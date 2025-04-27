from flask import Flask, redirect, request, session, url_for, render_template
import requests
import os
from datetime import timedelta
from dotenv import load_dotenv
import json
from datetime import datetime
import urllib.parse
import subprocess

#LOG ADD add_log(session['user']["global_name"],"msg")

app = Flask(__name__)
load_dotenv()

CLIENT_SECRET = os.getenv("CLIENT_SECRET")
CLIENT_ID = os.getenv("CLIENT_ID")
app.secret_key = os.getenv("SECRET_KEY")
REDIRECT_URI = os.getenv("FLASK_URL")+"callback"
PORT=int(os.getenv("PORT"))

AUTH_URL = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=identify+guilds"

TOKEN_URL = 'https://discord.com/api/oauth2/token'
API_URL = 'https://discord.com/api/users/@me'
GUILDS_API_URL = 'https://discord.com/api/users/@me/guilds'

app.permanent_session_lifetime = timedelta(days=60)  # 任意の期間に変更可

def get_container():
    result = subprocess.run(
        ["pct", "list"],
        capture_output=True,
        text=True
    )
    lines = result.stdout.splitlines()
    coutainers= []
    for line in lines:
        if not line[0]=="7":
            continue
        line_list=line.replace("                 ",",").replace("        ",",").split(",") #カンマ区切りのlist
        coutainers.append({
            "container_id":line_list[0],
            "container_status":line_list[1],
            "container_name":line_list[2]
        })
    return coutainers

def add_log(user,message):
    with open('web_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d-%H-%M')}::{user}::{message}\n")

@app.route('/pg1')
def pg1():
    ###正規チェック
    if 'user' not in session:
        return '<a href="/login">Discordでログイン</a>'
    ###正規チェック
    with open("allow_machine.json","r",encoding="utf-8") as f:
        machines = json.load(f)
    allow_machine_ids=[]
    for machine in machines: #そのユーザの許可されたmachine_idのリストを生成
        if session["user"]["id"] in machine["user"]:
            allow_machine_ids.append(machine["machine_id"])
    status_list=get_container()
    result=[]
    for allow_machine in allow_machine_ids:
        for status in status_list:
            if allow_machine == status["container_id"]:
                result.append(status)
    body="""<table>
            <tr>
                <th>コンテナ番号</th>
                <th>コンテナ名</th>
                <th>現在の状態</th>
                <th>動作</th>
            </tr>
            """
    for mm in result:
        body+=f"""
        <tr>
            <td>{mm["container_id"]}</td>
            <td>{mm["container_name"]}</td>
            <td>{mm["container_status"]}</td>
            <td><a href="/pg2?container_id={mm["container_id"]}&container_status={mm["container_status"]}">電源ボタンを押す</a></td>
        </tr>
        """
    body+="</table>"
    addstyle="""
        table {
      border-collapse: collapse;
      width: 100%;
    }
    th, td {
      border: 1px solid #333;
      padding: 8px;
      text-align: center;
    }
    th {
      background-color: #f2f2f2;
    }
    """
    return render_template("base.html",title=f"あなた操作可能なコンテナ",body=body,addstyle=addstyle)


@app.route("/pg2",methods=['GET', 'POST'])
def pg2():
    ###正規チェック
    if 'user' not in session:
        return '<a href="/login">Discordでログイン</a>'
    ###正規チェック
    if request.method == 'POST':
        container_id = request.form.get('container_id')
        container_status = request.form.get('container_status')
        ###
        status_list=get_container() 
        checked=False
        for status in status_list:
            if status["container_id"]==container_id:
                if status["container_status"]==container_status:
                    checked=True
        if checked==False:
            return "もう一度読み込んでください"
        ### 最新の情報かチェック
        if container_status=="running":
            switch_to="stop"
        elif container_status=="stopped":
            switch_to="start"
        else:
            return "異常エラー"
        try:
            subprocess.run(["pct", switch_to, container_id], check=True)
        except subprocess.CalledProcessError as e:
            return(f"コンテナ{switch_to}に失敗しました: {e}")
        body=f"コンテナ {container_id} を{switch_to}しました。"
        msg=f"{container_id}::{container_status}->>{switch_to}"
        add_log(session['user']["global_name"],msg)
        
        return render_template("base.html",title=f"操作成功",body=body)
    elif request.method == 'GET':
        container_id = request.args.get('container_id')
        container_status = code = request.args.get('container_status')
        status_list=get_container()
        checked=False
        for status in status_list:
            if status["container_id"]==container_id:
                if status["container_status"]==container_status:
                    checked=True
        if checked==False:
            return "もう一度読み込んでください"
        if container_status=="running":
            switch_to="停止"
        elif container_status=="stopped":
            switch_to="起動"
        else:
            return "異常エラー"
        body=f"""
        <form method="POST" action="/pg2">
            <input type="hidden" name="container_id" value="{container_id}">
            <input type="hidden" name="container_status" value="{container_status}">
            <button type="submit">する！</button>
        </form>
        """
        return render_template("base.html",title=f"{container_id}の電源を{switch_to}にしますか？",body=body)
          

@app.route('/')
def home():
    if 'user' not in session:
        return '<a href="/login">Discordでログイン</a>'
    user = session['user']
    return redirect(url_for("pg1"))

@app.route('/login')
def login():
    return redirect(AUTH_URL)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return '<a href="/login">Discordでログイン</a>'
    # トークンを取得
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'scope': "identify"
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    response = requests.post(TOKEN_URL, data=data, headers=headers)
    token_json = response.json()
    access_token = token_json.get('access_token')

    if not access_token:
        return '<a href="/login">Discordでログイン</a>'

    # ユーザー情報を取得
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    user_response = requests.get(API_URL, headers=headers)
    user_data = user_response.json()

    session.permanent = True
    session['user'] = user_data
    add_log(session['user']["global_name"],"login")
    return redirect(url_for("pg1"))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(port=PORT,host="0.0.0.0",debug=True)