from flask import Flask, render_template, redirect, url_for, request, jsonify, session
from supabase import create_client, Client
import os
import bcrypt
import json
import csv

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

@app.route('/')
def index():
     #return render_template('my_page.html')
    return render_template('index.html')
    #return jsonify({"message": "연동"})

@app.route('/go',methods=['POST'])
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
    
@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        balance = supabase.table('user_data').select('balance').eq('user_id', session['user_id']).execute() #user_data 테이블의 balance 열 중 user_id가 session['user_id']인 행을 가져옴
        total_assets = supabase.table('user_data').select('total_assets').eq('user_id', session['user_id']).execute() #user_data 테이블의 total_assets 열 중 user_id가 session['user_id']인 행을 가져옴
        stock_data = supabase.table('user_data').select('*').eq('user_id', session['user_id']).execute()
        stock_price_data = supabase.table('stock_data').select('*').order('id', desc=True).limit(1).execute()
        stock = list(stock_data.data[0].keys() if stock_data.data else [])[4:]
        stock_num = list(stock_data.data[0].values() if stock_data.data else [])[4:]
        stock_price=list(stock_price_data.data[0].values() if stock_price_data.data else [])[2:]
        return render_template('my_page.html', username=session['username'] , balance=balance.data[0]['balance'], total_assets=total_assets.data[0]['total_assets'], stock= stock, stock_num=stock_num, stock_price=stock_price)

    else:
        return redirect(url_for("login"))
    
@app.route('/logout')
def logout():
    session.clear() 
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
        response = supabase.table("users").insert(data).execute() #!! 주의 !! --> 데이터베이스에서 테스트 하다가 user_data랑 users의 id값 추가되는게 다를경우, 오류남!!!! 반드시 id 마지막 값 맞춰둘 것!!!!
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
    stock = list(stock_data.data[0].keys() if stock_data.data else [])[4:]
    stock_num = list(stock_data.data[0].values() if stock_data.data else [])[4:]
    stock_price=list(stock_price_data.data[0].values() if stock_price_data.data else [])[2:]
    return render_template('my_page.html', username=session['username'] , balance=balance.data[0]['balance'], total_assets=total_assets.data[0]['total_assets'], stock= stock, stock_num=stock_num, stock_price=stock_price)

def get_description_by_club(club_name):
    # CSV 파일 경로와 인코딩(UTF-8)을 확인합니다.
    with open('static\Club_detail_rows.csv', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['club_name'] == club_name:
                return row['description']
    return None

@app.route('/buy_stock', methods=['POST'])
def process_buy_stock():
    # 폼 데이터 받기
    club = request.form.get('club')
    amount_str = request.form.get('amount')
    if not club or not amount_str:
        return "club과 구매 수량이 필요합니다.", 400
    try:
        amount = int(amount_str)
    except ValueError:
        return "구매 수량은 숫자여야 합니다.", 400

    # recent_stock_data 테이블에서 최신 주식 가격 조회
    response = supabase.table('recent_stock_data') \
                       .select("*") \
                       .order("timestamp", desc=True) \
                       .limit(1) \
                       .execute()
    if not response.data:
        return "최신 주식 데이터가 없습니다.", 400

    recent_data = response.data[0]
    if club not in recent_data:
        return f"주식 데이터에 '{club}' 클럽 정보가 없습니다.", 400

    try:
        price = float(recent_data[club])
    except ValueError:
        return "주식 가격 데이터에 오류가 있습니다.", 400

    total_cost = price * amount

    # 세션에서 로그인된 사용자의 user_id 가져오기
    user_id = session.get('user_id')
    if not user_id:
        return "로그인된 사용자가 없습니다.", 401

    # user_data 테이블에서 user_id로 사용자 데이터 조회
    user_response = supabase.table('user_data') \
                            .select("*") \
                            .eq("user_id", user_id) \
                            .execute()
    if not user_response.data:
        return "사용자 데이터를 찾을 수 없습니다.", 404

    user_data = user_response.data[0]
    try:
        current_balance = float(user_data['balance'])
    except ValueError:
        return "계좌 잔액 데이터 오류", 400

    if current_balance < total_cost:
        return "잔액이 부족합니다.", 400

    # 잔액 차감 및 해당 클럽의 보유 주식 수 업데이트
    new_balance = current_balance - total_cost
    current_stock = int(user_data.get(club, 0))
    new_stock = current_stock + amount

    update_data = {
        "balance": new_balance,
        club: new_stock
    }

    update_response = supabase.table('user_data') \
                              .update(update_data) \
                              .eq("user_id", user_id) \
                              .execute()
    # if update_response.status_code != 200:
        # return "계좌 업데이트에 실패했습니다.", 500

    return f"구매 성공: '{club}' 주식 {amount}주를 {total_cost}원에 구매했습니다."
    
# @app.route('/stock')
# def my_page():
    # clubs=['세미콜론','실험의숲','그레이스','뉴턴','다독다독','데이터무제한','디세뇨','디아리오','메시스트','빌리네어','소솜','심쿵','아리솔','에스쿱','에어로테크','엘리제','온에어','티아','파라미터','피지카스트로','하람','늘품','세븐일레븐','매드매쓰','도담','데카르트','수학에복종','아페토','메이키스','폴리머','라온제나','리사','아스클레오피스','수북수북','아이티아이','럭스','쿠데타','헥사곤','개벽','혜윰']
    # return render_template('main_stock.html', username=session['username'], clubs=clubs)

@app.route('/buy_stock/<club>') #동아리 상세페이지
def buy_stock(club):
    description = get_description_by_club(club)
    balance = supabase.table('user_data').select('balance').eq('user_id', session['user_id']).execute() #user_data 테이블의 balance 열 중 user_id가 session['user_id']인 행을 가져옴
    clubs=['세미콜론','실험의숲','그레이스','뉴턴','다독다독','데이터무제한','디세뇨','디아리오','메시스트','빌리네어','소솜','심쿵','아리솔','에스쿱','에어로테크','엘리제','온에어','티아','파라미터','피지카스트로','하람','늘품','세븐일레븐','매드매쓰','도담','데카르트','수학에복종','아페토','메이키스','폴리머','라온제나','리사','아스클레오피스','수북수북','아이티아이','럭스','쿠데타','헥사곤','개벽','혜윰']
    # 최근 데이터를 timestamp를 기준으로 내림차순 정렬하여 첫 번째 row만 가져옵니다.
    response = supabase.table('recent_stock_data') \
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

    return render_template('buy_stock.html', clubs=clubs, club = club, description=description,stock_value=stock_value, balance=balance.data[0]['balance'])


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
def ranking() :

    return render_template('ranking.html', username=session['username'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 