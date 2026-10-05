import os
import glob
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

# Document Loaders and Splitters
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Azure Vector Store & Embeddings
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

# 1. Setup Logging & Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("indexer")

def index_docs():
    """Read PDFs, split their text into chunks, and upload them to Azure AI Search."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(current_dir, "../../backend/data")

    logger.info("Starting document indexing")
    logger.debug(
        "Embedding deployment=%s, Azure OpenAI API version=%s",
        os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
        os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
    )

    required_vars = (
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_API_KEY",
        "AZURE_SEARCH_INDEX_NAME",
    )
    missing_vars = [name for name in required_vars if not os.getenv(name)]
    if missing_vars:
        logger.error("Missing required environment variables: %s", missing_vars)
        logger.error("Please check your .env file and ensure all variables are set.")
        return

    try:
        logger.info("Initializing Azure OpenAI Embeddings...")
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv(
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
                "text-embedding-3-small",
            ),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        )
        logger.info("✓ Embeddings model initialized successfully")
    except Exception as error:
        logger.error("Failed to initialize embeddings: %s", error)
        logger.error("Please verify your Azure OpenAI deployment name and endpoint.")
        return

    try:
        logger.info("Initializing Azure AI Search vector store...")
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
        vector_store = AzureSearch(
            azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            azure_search_key=os.getenv("AZURE_SEARCH_API_KEY"),
            index_name=index_name,
            embedding_function=embeddings.embed_query,
        )
        logger.info(f"✓ Vector store initialized for index: {index_name}")
    except Exception as error:
        logger.error("Failed to initialize Azure Search: %s", error)
        logger.error("Please verify your Azure Search endpoint, API key, and index name.")
        return

    pdf_files = glob.glob(os.path.join(data_folder, "*.pdf"))
    if not pdf_files:
        logger.warning("No PDFs found in %s. Please add files.", data_folder)
        return

    pdf_names = [os.path.basename(pdf_path) for pdf_path in pdf_files]
    logger.info("Found %d PDFs to process: %s", len(pdf_files), pdf_names)

    all_splits = []

    for pdf_path in pdf_files:
        try:
            pdf_name = os.path.basename(pdf_path)
            logger.info("Loading: %s...", pdf_name)

            raw_docs = PyPDFLoader(pdf_path).load()
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
            )
            splits = text_splitter.split_documents(raw_docs)

            for split in splits:
                split.metadata["source"] = pdf_name

            all_splits.extend(splits)
            logger.info(" -> Split into %d chunks.", len(splits))
        except Exception as error:
            logger.error("Failed to process %s: %s", pdf_path, error)

    if all_splits:
        logger.info(
            "Uploading %d chunks to Azure AI Search index '%s'...",
            len(all_splits),
            index_name,
        )
        try:
            vector_store.add_documents(documents=all_splits)
            logger.info("=" * 60)
            logger.info("✅ Indexing Complete! The Knowledge Base is ready.")
            logger.info("Total chunks indexed: %d", len(all_splits))
            logger.info("=" * 60)
        except Exception as error:
            logger.error("Failed to upload documents to Azure Search: %s", error)
            logger.error("Please check your Azure Search configuration and try again.")
    else:
        logger.warning("No documents were processed.")

if __name__ == "__main__":
    index_docs()
