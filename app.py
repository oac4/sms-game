from flask import Flask, request
from sqlalchemy import create_engine
from sqlalchemy import text as prepare
from twilio import twiml
from twilio.rest import Client
import jsonpickle
import random
from apscheduler.schedulers.background import BackgroundScheduler


app = Flask(__name__)
sql_alchemy_engine = create_engine('mysql://sms_game:sms_pw@localhost:3306/sms_game', pool_recycle=3600, echo=False)

account_sid=""
account_token=""
our_number=""
client=Client(account_sid,account_token)

messages = {}
with open('questions.json','r') as file:
    messages = jsonpickle.decode(file.read())

@app.route("/")
def hello():
    return "<h1 style='color:blue'>Hello There!</h1>"

@app.route("/sms",methods=['POST'])
def sms():
    conn = sql_alchemy_engine.connect()
    number = request.form['From']
    message = request.form['Body']
    sql = """INSERT INTO messages ('phone','message')
        VALUES (:phone, :message)"""
    conn.execute(prepare(sql),{'phone':number,'message':message})
    sql = """SELECT * FROM conclave2020.registration"""
    sql = """SELECT * FROM game WHERE phone = :phone"""
    result = conn.execute(prepare(sql),{'phone':number})
    found = False
    for row in result:
        found = True
        current_round = row['current_round']
        answer = message.lower()
        answer = re.sub('[^a-z0-9]', '', answer)
        correct = False
        for a in messages[int(current_round)]['answers']:
            if a in answer:
                correct = True
        if correct:
            sql = """UPDATE `game` SET `q{}` = 1
                WHERE phone=:phone""".format(current_round)
            conn.execute(prepare(sql),{'phone':number})
            current_answers = [0]*8
            current_answers[int(current_round)] = 1
            for answer in current_answers:
                if row['q'+str(int(answer)+1)] == 1:
                    answer = 1
            unanswered_questions = []
            for a in range(0,8):
                if current_answers[a]==0:
                    unanswered_questions.append(a)
            if len(unanswered_questions)==0:
                sql = """UPDATE `game` SET `current_round` = 0,
                    `current_hint` = 0
                    WHERE phone=:phone"""
                conn.execute(prepare(sql),{'phone':number})
                sql = """SELECT COUNT(1) AS c FROM game
                    WHERE q1=1 AND q2=1
                    AND q3=1 AND q4=1
                    AND q5=1 AND q6=1
                    AND q7=1 AND q8=1
                    """
                completed = conn.execute(prepare(sql)).fetchone()['c']
                sql = """UPDATE `game` SET `rank` = :completed
                    WHERE phone=:phone"""
                conn.execute(prepare(sql),{'completed':completed,'phone':number})
                if int(c)==0:
                    message = "Congratulations! You are the first to complete the challenge! Your code is xxxxx"
                else:
                    message = "Congratulations on completing the challenge. Unfortunately, you were number {}.".format(c)
                client.messages.create(
                    body=message,
                    from_=our_number,
                    to=number
                )
            else:
                new_qustion = random.choice(unanswered_questions)
                sql = """UPDATE `game` SET `current_round` = :current_round,
                    `current_hint` = 0
                    WHERE phone=:phone"""
                conn.execute(prepare(sql),{'phone':number,'current_round':new_qustion})
                client.messages.create(
                    body=messages[new_question-1][0],
                    from_=our_number,
                    to=number
                )
        else:
            client.messages.create(
                body='wrong answer, try again',
                from_=our_number,
                to=number
            )
    if not found:
        message = "Welcome to the C-4 Conclave Game Competition! There are 8 questions, one for each Lodge. You will receive your first question next. Each question will have five clues. Each clue will be sent to you after 5 minutes. Once you correcrly guess the answer, you will receive your next question. The first one to compete it will win an Amazon gift card."
        client.messages.create(
            body=message,
            from_=our_number,
            to=number
        )
        n = random.randint(1,8)
        sql = """INSERT INTO `game`(`phone`, `current_round`, `current_hint`) VALUES
        (:phone,:current_round,0)"""
        conn.execute(prepare(sql),{'phone':number,'current_round':n})
        client.messages.create(
            body=messages[n-1][0],
            from_=our_number,
            to=number
        )
    conn.close()
    return ''

if __name__ == "__main__":
    app.run(host='0.0.0.0')


def scheduled_task():
    conn = sql_alchemy_engine.connect()
    sql = """SELECT * from game WHERE ts<NOW()-INTERVAL 5 MINUTE
    AND current_round!=0 """
    result = conn.execute(prepare(sql))
    for row in result:
        nexthint = int(row['current_hint'])
        if len(messages[row['current_round']-1])>nexthint:
            sql = """UPDATE game SET current_hint = :nexthint
                WHERE phone=:phone"""
            conn.execute(prepare(sql),{'phone':row['phone'],'nexthint':nexthint})
            client.messages.create(
                body=messages[row['current_round']-1][nexthint],
                from_=our_number,
                to=row['phone']
            )
    conn.close()

scheduler = BackgroundScheduler(timezone='utc')
scheduler.add_job(func=scheduled_task, trigger="interval", second=15)
scheduler.start()
