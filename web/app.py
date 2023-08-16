from flask import Flask, jsonify, request
from flask_restful import Api, Resource
from pymongo import MongoClient
import bcrypt
import numpy
import tensorflow as tf
import requests

from keras.applications import InceptionV3
from keras.applications.inception_v3 import preprocess_input
from keras.applications import imagenet_utils
from keras.preprocessing.image import img_to_array
from PIL import Image
from io import BytesIO
import pandas as np





app = Flask(__name__)
api = Api(app)

# Load th pre trained model
pretrained_model = InceptionV3(weights="imagenet")



#initianlioze the MongoClient
client = MongoClient("mongodb://db:27017")

# create a new db and collection
db = client.ImageRecognition
users = db["Users"]




def UserExist(username):
    return False if users.count_documents({"Username":username}) == 0 else True

class Register(Resource):
    def post(self):
        #Step 1 is to get posted data by the user
        postedData = request.get_json()

        #Get the data
        username = postedData["username"]
        password = postedData["password"] #"123xyz"

        if UserExist(username):
            return jsonify({
                'status':301,
                'msg': 'Invalid Username'
            })
        # check if user is new , hash password
        hashed_pw = bcrypt.hashpw(password.encode('utf8'), bcrypt.gensalt())
        #Store username and pw into the database
        
        users.insert_one({
            "Username": username,
            "Password": hashed_pw,
            "Tokens":10
        })

        retJson = {
            "status": 200,
            "msg": "You successfully signed up for the API"
        }
        return jsonify(retJson)
    
def verifyPw(username, password):
    if not UserExist(username):
        return False

    hashed_pw = users.find({
        "Username":username
    })[0]["Password"]

    if bcrypt.hashpw(password.encode('utf8'), hashed_pw) == hashed_pw:
        return True
    else:
        return False
    
def generateReturnDictionary(status, msg):
    retJson = {
        "status": status,
        "msg": msg
    }
    return retJson
    
def verifyCredentials(username, password):
    if not UserExist(username):
        return generateReturnDictionary(301, "Invalid Username"), True

    correct_pw = verifyPw(username, password)

    if not correct_pw:
        return generateReturnDictionary(302, "Incorrect Password"), True

    return None, False
    
class Classify(Resource):
    def post(self):
        #get posted data
        postedData = request.get_json()

        username = postedData["username"]
        password = postedData["password"]
        url = postedData["url"]

        # check credentials
        retJson, error = verifyCredentials(username, password)

        if error:
            return jsonify(retJson)
        
        # check if user has tokens
        tokens = users.find({
            "Username":username
        })[0]["Tokens"]

        if tokens<=0:
            return jsonify(generateReturnDictionary(303, "Not Enough Tokens"))
        
        # classify the image

        if not url:
            return jsonify(({"error":"No url provided"}),400)
        
        # load image from url
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))


        # pre process the image
        img = img.resize((299,299))
        img_array = img_to_array(img)
        img_array = np.expand_dims(img_array, axis = 0)
        img_array = preprocess_input(img_array)

        # make prediction
        prediction = pretrained_model.predict(img_array)
        actual_prediction = imagenet_utils.decode_predictions(prediction, top = 5)

        
        # return classification response
        ret_json = {}

        for pred in actual_prediction[0]:
            ret_json[pred[1]] = float(pred[2]*100)
        
        # reduce token / user hat less service

        users.update_one({
            "Username":username
        }),{
            "$set":{
                "Tokes":tokens-1
            }
        }

        return jsonify(ret_json)

class Refill(Resource):
    def post(self):
        # Get posted data
        postedData = request.get_json()

        # get credentials
        username = postedData["username"]
        password = postedData["admin_pw"]
        amount = postedData["amount"]

        # check if the user exists
        if not UserExist(username):
            return jsonify(generateReturnDictionary(301, "Invalid Username"))


        correct_pw = "abc123" # we schoud get the correct passwoerd from the database
        if not password == correct_pw:
            return jsonify(generateReturnDictionary(302, "Incorrect Password"))

        users.update_one({
            "Username": username
        },{
            "$set":{
                "Tokens": amount
            }
        })
        return jsonify(generateReturnDictionary(200, "Refilled"))

        

    

# user register enpoint       
api.add_resource(Register, '/register')
api.add_resource(Classify, '/classify')
api.add_resource(Refill, '/refill')

if __name__=="__main__":
    app.run(host='0.0.0.0')



