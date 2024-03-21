import requests
from services.alerts import baseAlerts

class telegram(baseAlerts):
    def __init__(self, 
                 tg_chat_id: str , 
                 tg_api_token: str, 
                 email_recipient: list = None):
        self.chat_id = tg_chat_id
        self.api_token = tg_api_token
        self.email_recipients = email_recipient
        self.data_dict = {
            'chat_id': str(self.chat_id),
            'parse_mode': 'markdown',
            'disable_notification': False,}
        self.url = f'https://api.telegram.org/bot{self.api_token}/sendMessage'
    
    def info(self, message):
        self.data_dict['text'] = str(message)
        return requests.post(self.url, json=self.data_dict)
    
    def warning(self, message):
        self.data_dict['text'] = "*WARNING*: "+ str(message)
        return requests.post(self.url, json=self.data_dict)

    def error(self, message):
        self.data_dict['text'] = "*ERROR*: " + str(message)
        return requests.post(self.url, json=self.data_dict)
        

