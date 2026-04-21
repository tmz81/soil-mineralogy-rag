import os
import sys
from dotenv import load_dotenv

print(f"Python version: {sys.version}")

try:
    from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
    print("✓ langchain_community.document_loaders: OK")
    
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    print("✓ langchain_text_splitters: OK")
    
    from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
    print("✓ langchain_google_genai: OK")
    
    from langchain_chroma import Chroma
    print("✓ langchain_chroma: OK")
    
    from langchain.chains import RetrievalQA
    print("✓ langchain.chains: OK")
    
    from langchain.prompts import PromptTemplate
    print("✓ langchain.prompts: OK")
    
    import pypdf
    print("✓ pypdf: OK")
    
    import dotenv
    print("✓ python-dotenv (dotenv): OK")
    
    print("\nAll imports verified successfully!")
    
except ImportError as e:
    print(f"\n✗ Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ An unexpected error occurred: {e}")
    sys.exit(1)
