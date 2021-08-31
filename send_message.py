


import requests

def telegram_bot_sendtext(bot_message, chat_id):
   # bot_token = '1800200991:AAFk9Jd617Zwmxv-BSBDKedqZR4vz6AFZko'
    bot_token = '1954926322:AAFdFo4By1OZrv-044XlKuxWZ3sf_glCVxU'
    bot_chatID = chat_id
    send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message

    response = requests.get(send_text)

    return response.json()

