from flask import Flask, render_template, redirect, url_for, request, jsonify, session
from supabase import create_client, Client
import os
import bcrypt
import json
import csv
from apscheduler.schedulers.background import BackgroundScheduler
import random
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import numpy as np

sigma = 0.7 #표준편차(변동성) 일단 2%
k = 0.5 #기본 주식 가격 변동률(가중치) 일단 10%
#비밀번호 암호화해서 저장
#근뎅 bcrypt첨 해봐서 뭔지 잘 모르겟엉
def hashing(pw):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pw.encode(), salt)
    return hashed.decode()

#비번 확인
def verify_password(input_password, stored_hash):
    return bcrypt.checkpw(input_password.encode(), stored_hash.encode())

app = Flask(__name__)
app.secret_key="secret_key"

SUPABASE_URL="https://lwjodduasieisebkrusp.supabase.co"
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx3am9kZHVhc2llaXNlYmtydXNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzg2NDA0NjMsImV4cCI6MjA1NDIxNjQ2M30.3HaCNzho2G-mCYScAKVI2XuF4U24fSJqiVhEQZOtr4I"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def convert_to_serializable(obj):
    """🔄 JSON 직렬화가 가능한 타입으로 변환"""
    if isinstance(obj, (pd.Int64Dtype, pd.Float64Dtype)):
        return int(obj)
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj

def profit_rate(cP, aP):
    return f'{round((cP - aP) / aP, 2)}%'

def update_stock_prices():
    """🔄 10초마다 주식 가격을 새로운 행으로 추가하여 기록"""
    # 📥 Supabase에서 가장 최근 데이터 가져오기
    response = supabase.table("stock_data") \
                       .select("*") \
                       .order("timestamp", desc=True) \
                       .limit(1) \
                       .execute()
    records = response.data

    response_supply_demand = supabase.table("supply_demand")\
                                     .select("*")\
                                     .execute()
    supply_demand = response_supply_demand.data

    if not records or not supply_demand:
        print("⚠️ 테이블에 데이터가 없습니다.")
        return

   # 최근 데이터를 DataFrame으로 변환
    df = pd.DataFrame(records)
    #랜덤 변동성(정규분포)
    # ✅ 새 데이터 생성
    new_data = {"timestamp": datetime.now().isoformat()}
    club_name=set([row['club_name'] for row in supply_demand])
    # ✅ 가격 변동 적용 (-2000 ~ +2000)
    for col in df.columns[2:]:  # id, timestamp 제외
        base_price = df.iloc[0][col]
        if col in club_name:
            print(col)
            epsilon = np.random.normal(0, sigma)
            demand = [int(row['demand']) for row in supply_demand if row['club_name'] == col]
            supply = [int(row['supply']) for row in supply_demand if row['club_name'] == col]
            non_zero_supply = max(sum(supply), 1)  # 0으로 나누는 오류 방지
            new_price = base_price*(sum(demand)/non_zero_supply)**k * np.exp(epsilon) +1
            print(f"k={k} demand={demand}, supply={supply}")
            print(f"k={k}기존 가격: {base_price}, 변동 비율: {(sum(demand) / non_zero_supply) ** k}, 최종 변동: {np.exp(epsilon)}")
            print(new_price)
        else:
            new_price = max(int(base_price) + random.randint(-2000, 2000), 1000)
        new_data[col] = int(new_price)  # int64 → int 변환
    #supply_demand 초기화
    supabase.table("supply_demand").delete().gt("id", 0).execute()
    #test supplydemand에 임의의 값 추가------------------------------------------------------------------
    random_test_case1={
        "user_id":1, 
        "club_name" :'세미콜론',
        "supply": random.randint(1,500),
        "demand": random.randint(1,500)
    }
    random_test_case2={
        "user_id":1, 
        "club_name" :'실험의숲',
        "supply": random.randint(1,500),
        "demand": random.randint(1,500)
    }
    supabase.table("supply_demand").insert(random_test_case1).execute()
    supabase.table("supply_demand").insert(random_test_case2).execute()
    #---------------------------------------------------------------------------------------------------
    # ✅ 모든 값 직렬화 가능하도록 변환
    new_data = {k: convert_to_serializable(v) for k, v in new_data.items()}

    # 🔄 Supabase에 **새로운 행 추가**
    supabase.table("stock_data").insert(new_data).execute()

    print(f"✅ [{new_data['timestamp']}] 주식 가격 추가 완료!")
# 🕒 스케줄러 설정: 10초마다 실행
scheduler = BackgroundScheduler()
scheduler.add_job(update_stock_prices, "interval", seconds=10000000)#test
scheduler.start()



@app.route('/')
def index():
     #return render_template('my_page.html')
    return render_template('index.html')
    #return jsonify({"message": "연동"})

@app.route('/go',methods=['POST', 'GET'])
def go():
    return render_template('login.html')

@app.route('/register',methods=['POST'])
def register():
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def main():
    student_id = request.form.get('student_id')
    pw = request.form.get('pw')

    user_data = supabase.table('users').select('*').eq('student_id',student_id ).execute() #user_data 테이블에서 모든 행의 student_id가 입력받은 student_id인 행을 가져옴

    if user_data.data:
        user=user_data.data[0]
        stored_pw = user['password_hash']
    
        if verify_password(pw, stored_pw):
            session['user_id'] = user['student_id']
            session['username'] = user['username']
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", response_pw="비밀번호가 일치하지 않습니다.", id=student_id)
    else:
        return render_template("login.html", response="아이디가 존재하지 않습니다.")

@app.route('/logout')
def logout():
    session.clear() 
    return redirect(url_for("go"))

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        balance = supabase.table('user_data').select('balance').eq('user_id', session['user_id']).execute() #user_data 테이블의 balance 열 중 user_id가 session['user_id']인 행을 가져옴
        total_assets = supabase.table('user_data').select('total_assets').eq('user_id', session['user_id']).execute() #user_data 테이블의 total_assets 열 중 user_id가 session['user_id']인 행을 가져옴
        stock_data = supabase.table('user_data').select('*').eq('user_id', session['user_id']).execute()
        stock_price_data = supabase.table('stock_data').select('*').order('id', desc=True).limit(1).execute()
        stock = list(stock_data.data[0].keys() if stock_data.data else [])[4:44]
        stock_num = list(stock_data.data[0].values() if stock_data.data else [])[4:44]
        stock_price=list(stock_price_data.data[0].values() if stock_price_data.data else [])[2:]
        return render_template('my_page.html', username=session['username'] , balance=balance.data[0]['balance'], total_assets=total_assets.data[0]['total_assets'], stock= stock, stock_num=stock_num, stock_price=stock_price)
      
    else:
        return redirect(url_for("login"))

@app.route('/register_data', methods=["POST"])
def re_main():
    ID = request.form.get('ID') # 학번
    USERNAME = request.form.get('USERNAME') # 아이디
    PW = request.form.get('PW') # 비밀번호
    PW_CHECK = request.form.get('PW_CHECK') # 비밀번호 확인
    AGREE = request.form.get('agree') # 체크박스 유무
    recheck = False
    res = ''
    resPW = ''
    resAgree = ''
    #유저가 이미 있는지 식별
    existing_user = supabase.table("users").select("student_id, username")\
        .or_(f"student_id.eq.{ID}, username.eq.{USERNAME}")\
        .execute()
    # 중복 유저 존재 시
    if existing_user.data:
        res = '이미 사용 중인 학번 또는 아이디입니다.'
        recheck = True
        ID = ''
        USERNAME =''
    # 비밀번호와 비밀번호 확인이 다를 시
    if PW != PW_CHECK:
        resPW='비밀번호가 일치하지 않습니다. 다시 입력하세요.'
        recheck = True
        PW = ''
        PW_CHECK = ''
    # 체크하지 않았을 시
    if AGREE != 'agree' :
        resAgree = '위 항목은 필수 항목입니다.'
        recheck = True
    # 다시 입력하라고 시키기
    if recheck :
        return render_template('register.html', response=res, response_pw=resPW, response_agree=resAgree, id=ID, username=USERNAME, pw=PW, pwCheck=PW_CHECK)
    PW = hashing(PW) #해싱처리
    data_stock={"user_id": ID} #초기 자본금 100만원
    data = {"student_id": ID,"username": USERNAME,"password_hash": PW} #데이터 삽입
    #db오류 시
    try:
        response = supabase.table("users").insert(data).execute()
        response_stock = supabase.table("user_data").insert(data_stock).execute()
        return render_template('login.html', ID=ID, USERNAME=USERNAME)    
    except Exception as e:
        return render_template('register.html', response=f"회원가입 실패: {str(e)}")
    
@app.route('/home')
def home():
    balance = supabase.table('user_data').select('balance').eq('user_id', session['user_id']).execute() #user_data 테이블의 balance 열 중 user_id가 session['user_id']인 행을 가져옴
    total_assets = supabase.table('user_data').select('total_assets').eq('user_id', session['user_id']).execute() #user_data 테이블의 total_assets 열 중 user_id가 session['user_id']인 행을 가져옴
    stock_data = supabase.table('user_data').select('*').eq('user_id', session['user_id']).execute()
    stock_price_data = supabase.table('stock_data').select('*').order('id', desc=True).limit(1).execute()
    stock = list(stock_data.data[0].keys() if stock_data.data else [])[4:44]
    stock_num = list(stock_data.data[0].values() if stock_data.data else [])[4:44]
    stock_price=list(stock_price_data.data[0].values() if stock_price_data.data else [])[2:]
    return render_template('my_page.html', username=session['username'] , balance=balance.data[0]['balance'], total_assets=total_assets.data[0]['total_assets'], stock= stock, stock_num=stock_num, stock_price=stock_price)

def get_description_by_club(club_name):
    # CSV 파일 경로와 인코딩(UTF-8)을 확인합니다.
    with open('static/Club_detail_rows.csv', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['club_name'] == club_name:
                # description을 쉼표로 분리한 후, 각 항목 앞에 '#' 추가
                return [f"#{desc.strip()}" for desc in row['description'].split(',')]
    return None

def get_longer_by_club(club_name):
    with open('static/Club_detail_rows.csv', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['club_name'] == club_name:
                return row['longer'].strip()  # `longer` 값 반환
    return None

@app.route('/buy_stock', methods=['POST'])
def process_buy_stock():
    # 폼 데이터 받기
    trade = request.form.get('trade') #trade는 'buy'아니면 'sell'
    club = request.form.get('club')
    amount_str = request.form.get('amount')
    print(club,'/' ,amount_str)
    if not club or not amount_str:
        return jsonify({"error":"club과 구매 수량이 필요합니다."}), 400
    try:
        amount = int(amount_str)
    except ValueError:
        return jsonify({"구매 수량은 숫자여야 합니다."}), 400

    # stock_data 테이블에서 최신 주식 가격 조회
    response = supabase.table('stock_data') \
                       .select("*") \
                       .order("timestamp", desc=True) \
                       .limit(1) \
                       .execute()
    if not response.data:
        return jsonify({"최신 주식 데이터가 없습니다."}), 400

    recent_data = response.data[0]
    if club not in recent_data:
        return jsonify({f"주식 데이터에 '{club}' 클럽 정보가 없습니다."}), 400

    try:
        price = float(recent_data[club])
    except ValueError:
        return jsonify({"주식 가격 데이터에 오류가 있습니다."}), 400

    total_cost = price * amount

    # 세션에서 로그인된 사용자의 user_id 가져오기
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"로그인된 사용자가 없습니다."}), 401

    # user_data 테이블에서 user_id로 사용자 데이터 조회
    user_response = supabase.table('user_data') \
                            .select("*") \
                            .eq("user_id", user_id) \
                            .execute()
    if not user_response.data:
        return jsonify({"사용자 데이터를 찾을 수 없습니다."}), 404

    user_data = user_response.data[0]
    try:
        current_balance = float(user_data['balance'])
    except ValueError:
        return jsonify({"계좌 잔액 데이터 오류"}), 400

    try:
        average_cost = float(user_data[club+'_평균구매가'])
    except ValueError:
        return jsonify({"평균 매수가 데이터 오류"}), 400
    
    try:
        current_amount = int(user_data[club])
    except ValueError:
        return jsonify({"주식 보유량 데이터 오류"}), 400

    if current_balance < total_cost:
        return jsonify({"잔액이 부족합니다."}), 400

    if trade=="buy":
        # 잔액 차감 및 해당 클럽의 보유 주식 수 업데이트
        new_balance = current_balance - total_cost
        current_stock = int(user_data.get(club, 0))
        average_cost = (average_cost*current_amount + total_cost) / (current_amount+amount)
    
        new_stock = current_stock + amount

        update_data = {
            "balance": new_balance,
            club: new_stock,
            club+'_평균구매가': average_cost
        }

        update_demand = {
            "club_name" : club,
            "supply" : 0,
            "demand" : amount,
            "user_id" : user_id #유저 아이디 추가 -> 보안용(대조군 생성성)
        }

        update_response = supabase.table('user_data') \
                                .update(update_data) \
                                .eq("user_id", user_id) \
                                .execute()
        
        update_response_demand = supabase.table('supply_demand') \
                                    .insert(update_demand) \
                                    .execute()
        print(update_demand)
        # if update_response.status_code != 200:
            # return "계좌 업데이트에 실패했습니다.", 500

        return jsonify({"message": f"매수 성공: '{club}' 주식 {amount}주를 {total_cost}원에 매수하였습니다."})

    else: #trade ==sell
        if int(user_data.get(club, 0)) < amount:
            return jsonify({"보유 주식이 부족합니다."}), 400  # 매도 수량 검증 추가
        # 잔액 차감 및 해당 클럽의 보유 주식 수 업데이트
        new_balance = current_balance + total_cost
        current_stock = int(user_data.get(club, 0))
        new_stock = current_stock - amount

        update_data = {
            "balance": new_balance,
            club: new_stock
        }

        update_demand = {
            "club_name" : club,
            "supply" : amount,
            "demand" : 0,
            "user_id" : user_id #유저 아이디 추가 -> 보안용(대조군 생성성)
        }

        update_response = supabase.table('user_data') \
                                .update(update_data) \
                                .eq("user_id", user_id) \
                                .execute()
        
        update_response_demand = supabase.table('supply_demand') \
                                    .insert(update_demand) \
                                    .execute()
        print(update_demand)
        # if update_response.status_code != 200:
            # return "계좌 업데이트에 실패했습니다.", 500

        return jsonify({"message": f"매도 성공: '{club}' 주식 {amount}주를 {total_cost}원에 매도하였습니다."})
# @app.route('/stock')
# def my_page():
    # clubs=['세미콜론','실험의숲','그레이스','뉴턴','다독다독','데이터무제한','디세뇨','디아리오','메시스트','빌리네어','소솜','심쿵','아리솔','에스쿱','에어로테크','엘리제','온에어','티아','파라미터','피지카스트로','하람','늘품','세븐일레븐','매드매쓰','도담','데카르트','수학에복종','아페토','메이키스','폴리머','라온제나','리사','아스클레오피스','수북수북','아이티아이','럭스','쿠데타','헥사곤','개벽','혜윰']
    # return render_template('main_stock.html', username=session['username'], clubs=clubs)

@app.route('/buy_stock/<club>') #동아리 상세페이지
def buy_stock(club):
    description = get_description_by_club(club)
    longer = get_longer_by_club(club)
    balance = supabase.table('user_data').select('balance').eq('user_id', session['user_id']).execute() #user_data 테이블의 balance 열 중 user_id가 session['user_id']인 행을 가져옴
    clubs=['세미콜론','실험의숲','그레이스','뉴턴','다독다독','데이터무제한','디세뇨','디아리오','메시스트','빌리네어','소솜','심쿵','아리솔','에스쿱','에어로테크','엘리제','온에어','티아','파라미터','피지카스트로','하람','늘품','세븐일레븐','매드매쓰','도담','데카르트','수학에복종','아페토','메이키스','폴리머','라온제나','리사','아스클레오피스','수북수북','아이티아이','럭스','쿠데타','헥사곤','개벽','혜윰']
    # 최근 데이터를 timestamp를 기준으로 내림차순 정렬하여 첫 번째 row만 가져옵니다.
    response = supabase.table('stock_data') \
        .select("*") \
        .order("timestamp", desc=True) \
        .limit(1) \
        .execute()

    # Supabase API 응답은 response.data에 row 리스트로 들어있습니다.
    recent_row = response.data[0] if response.data else None

    if recent_row:
        # club 변수와 같은 이름의 컬럼 값을 가져옵니다.
        stock_value = recent_row.get(club)
    else:
        stock_value = None

    return render_template('buy_stock.html', clubs=clubs, club = club, description=description,stock_value=stock_value, balance=balance.data[0]['balance'], longer = longer)


@app.route('/stock') #전체 주식 보기 페이지
def my_page():
    clubs=['세미콜론','실험의숲','그레이스','뉴턴','다독다독','데이터무제한','디세뇨','디아리오','메시스트','빌리네어','소솜','심쿵','아리솔','에스쿱','에어로테크','엘리제','온에어','티아','파라미터','피지카스트로','하람','늘품','세븐일레븐','매드매쓰','도담','데카르트','수학에복종','아페토','메이키스','폴리머','라온제나','리사','아스클레오피스','수북수북','아이티아이','럭스','쿠데타','헥사곤','개벽','혜윰']

    club_price_DB= supabase.table('stock_data').select('*').order('id', desc=True).limit(1).execute()
    club_price = list(club_price_DB.data[0].values()) if club_price_DB.data else []
    return render_template('main_stock.html', username=session['username'], clubs=clubs, club_price=club_price)

@app.route('/extra_buy', methods=['POST'])
def extra_buy():
    data = request.get_json()
    quantity = data.get('quantity')
    stock = data.get('stock')
    existing=supabase.table('user_data').select(stock).eq("user_id", session['user_id']).execute()
    existing_var= list(existing.data[0].values()) if existing.data else []
    new= int(existing_var[0])+int(quantity)
    supabase.table("user_data").update({stock: new}).eq("user_id", session['user_id']).execute()

    #JSON 응답 반환 (클라이언트 새로고침 수행 명령!)
    return jsonify({"message": f"매수 완료! 수량: {quantity}, 주식: {stock}"}), 200

@app.route('/sell', methods=['POST'])
def sell():
    data = request.get_json()
    quantity = data.get('quantity')
    stock = data.get('stock')
    existing=supabase.table('user_data').select(stock).eq("user_id", session['user_id']).execute()
    existing_var= list(existing.data[0].values()) if existing.data else []
    new= int(existing_var[0])-int(quantity)
    supabase.table("user_data").update({stock: new}).eq("user_id", session['user_id']).execute()

    #JSON 응답 반환 (클라이언트 새로고침 수행 명령!)
    return jsonify({"message": f"매도 완료! 수량: {quantity}, 주식: {stock}"}), 200

# 랭킹
@app.route('/ranking') 
def ranking():
    response = supabase.table('user_data') \
                       .select('user_id, total_assets') \
                       .order('total_assets', desc=True) \
                       .execute()
    if not response.data:
        return render_template('ranking.html', username=session['username'], ranking=[])
    
    # Fetch usernames for each user_id
    user_ids = [row['user_id'] for row in response.data]
    users_response = supabase.table('users') \
                             .select('student_id, username') \
                             .in_('student_id', user_ids) \
                             .execute()
    users = {user['student_id']: user['username'] for user in users_response.data}

    ranking = [
        {
            'username': users[row['user_id']],
            'total_assets': row['total_assets']
        }
        for row in response.data
    ]

    return render_template('ranking.html', username=session['username'], ranking=ranking)

@app.route('/stock_data/<club>')
def stock_data(club):
    response = supabase.table('stock_data') \
                       .select('timestamp, ' + club) \
                       .order('timestamp', desc=True) \
                       .limit(30) \
                       .execute()
    if not response.data:
        return jsonify({"dates": [], "prices": []})

    # Reverse the data to have the oldest first
    response.data.reverse()

    dates = [row['timestamp'] for row in response.data]
    prices = [row[club] for row in response.data]

    return jsonify({"dates": dates, "prices": prices})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)