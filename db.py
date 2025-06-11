from pymongo import MongoClient

# Replace with your MongoDB Atlas connection string
MONGO_URI = "mongodb+srv://test:test@cluster0.pwnfedw.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client["chatdatabase"]  # Replace with your database name
collection = db["chat"]  # Replace with your collection name