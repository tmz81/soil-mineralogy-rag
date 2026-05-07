import sys
from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

for path_name, path_val in [
    ("RAIZ", "/home/tmz81/www/soil-mineralogy-rag/chroma_db"),
    ("SRC", "/home/tmz81/www/soil-mineralogy-rag/src/chroma_db")
]:
    print(f"\nTestando: {path_name} ({path_val})")
    try:
        vectorstore = Chroma(persist_directory=path_val, embedding_function=embeddings)
        count = vectorstore._collection.count()
        print(f"Sucesso! Número de trechos na coleção: {count}")
    except Exception as e:
        print(f"Erro: {type(e).__name__}: {e}")
