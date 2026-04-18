import os
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import aiplatform
from dotenv import load_dotenv

load_dotenv()
project = os.environ.get("GCP_PROJECT")
location = os.environ.get("GCP_LOCATION", "us-central1")

print(f"Project: {project}")
print(f"Location: {location}")

vertexai.init(project=project, location=location)

try:
    print("Listing models (base)...")
    model = GenerativeModel("gemini-2.5-pro")
    # We can't easily "list" through the GenerativeModel class without a call, 
    # but we can try a very simple generate_content with a single word.
    response = model.generate_content("Hi")
    print(f"Success with gemini-1.5-pro-001: {response.text}")
except Exception as e:
    print(f"Failed with gemini-1.5-pro-001: {e}")

try:
    print("Trying gemini-1.5-flash...")
    model = GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("Hi")
    print(f"Success with gemini-1.5-flash: {response.text}")
except Exception as e:
    print(f"Failed with gemini-1.5-flash: {e}")
