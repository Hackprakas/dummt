from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient
from supabase import create_client, Client
from pydantic import BaseModel
from typing import Optional, List
import os
from dotenv import load_dotenv

app = FastAPI()
load_dotenv()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client["vaayusastra"]
users_collection = db["users"]
products_collection = db["products"]


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)



class TokenData(BaseModel):
    email: Optional[str] = None



async def get_user_from_token(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    
    user = await users_collection.find_one({"email": token_data.email})
    if user is None:
        raise credentials_exception

    return user



async def check_user_permissions(user: dict):
    if not user.get("emailss"):
        return {"error": "No user found."}
    else:
        print("nothing")

    
    permissions = user.get("permissions", {})

    if permissions.get("read") and permissions.get("write"):
        return {"users": "users"}
    elif permissions.get("read") and not permissions.get("write"):
        return {"error": "You do not have write access."}
    elif not permissions.get("read") and permissions.get("write"):
        return {"error": "You do not have read access."}
    return {"error": "You are not authorized to add users."}



async def upload_file_to_supabase(file: UploadFile):
    
    try:
        content = await file.read()
        file_name = file.filename
        res = supabase.storage.from_("vaayusastra2").upload(f"vaayusastra/{file_name}", content, {
            "contentType": "image/jpg"
        })
        public_url = supabase.storage.from_("vaayusastra2").get_public_url(f"vaayusastra/{file_name}")
        if res:
            return {"message": public_url}
    except Exception as e:
        return {"error": str(e)}



@app.post("/uploadproduct")
async def upload_product(
    name: str = Form(...),
    description: str = Form(...),
    main: UploadFile = File(...),
    stock: int = Form(...),
    price: float = Form(...),
    additionalImages: List[UploadFile] = File(...),
    user: dict = Depends(get_user_from_token)
):
    
    user_check = await check_user_permissions(user)
    if "users" in user_check:
        try:
            
            main_image_url = await upload_file_to_supabase(main)
            if "error" in main_image_url:
                return main_image_url

            
            additional_image_urls = []
            for image in additionalImages:
                image_url = await upload_file_to_supabase(image)
                additional_image_urls.append(image_url.get("message", {}).get("data", {}).get("publicUrl"))

            # Save product to MongoDB
            product = {
                "name": name,
                "description": description,
                "image": main_image_url.get("message", {}).get("data", {}).get("publicUrl"),
                "additional_images": additional_image_urls,
                "price": price,
                "stock": stock
            }
            await products_collection.insert_one(product)

            return {"message": "Product added successfully"}
        except Exception as e:
            return {"error": str(e)}
    else:
        return user_check
