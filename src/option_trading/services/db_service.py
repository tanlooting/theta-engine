from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import logging

 
class DBService:
    def __init__(self, auth_config, logger: logging.Logger):
        self.username = auth_config['mdb_username']
        self.password = auth_config['mdb_password']
        self.cluster = auth_config['mdb_cluster']
        self.logger = logger
        self.uri = f"mongodb+srv://{self.username}:{self.password}@{self.cluster}.te4j5pb.mongodb.net/?retryWrites=true&w=majority"
        self.client = MongoClient(self.uri, server_api=ServerApi('1'))
        self.connect()
    
    def connect(self):
        try:
            self.ping()
            return self.client
        except ConnectionFailure as e:
            print("unsuccessful connection to DB")
            self.logger.error(f"MongoDB connection failure: {e}")
        
    def ping(self, 
             msg= "You successfully connected to MongoDB!"):
        try:
            self.client.admin.command('ping')
            print("successful connection to DB.")
        except Exception as e:
            print(e)
        
        
    def get_database(self, db_name):
        self.db = self.client[db_name]
        return self.db
    
    def disconnect(self):
        self.client.close()
        