########### IMPORTANT: Change name of this file to config.py ##############


# Database connection details
DB_USER = "AIUSER" # Username
DB_PWD = "your-password" # Password
DB_HOST_IP = "adb.us-chicago-1.oraclecloud.com" # stable
DB_SERVICE = "livelabvs_medium"
CONFIG_DIR = "/wallet/config/dir" # likely same as below
WALLET_LOCATION = "/path/to/your/wallet"
WALLET_PASSWORD = "your_wallet_password" # 

# GenAI configurations
PROFILE_NAME = "DEFAULT" # OCI Authentication profile name change if not DEFAULT
COMPARTMENT_OCID = "<your-compartment-ocid>" # same compartment as ADB
ENDPOINT = "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com" # stable
COHERE_API_KEY = "<your-cohere-api-key>" # Cohere Reranker api key: https://cohere.com

# Verbosity setting
VERBOSE = False

# Whether to stream chat messages or not
STREAM_CHAT = False

# Embedding model type
EMBED_MODEL_TYPE = "OCI" # DB or OCI

# Embedding model for generating embeddings
# If using in-database embeddings, Name of the embedding model inside the DB
EMBED_MODEL = "cohere.embed-english-v3.0"

# Tokenizer for token counting
TOKENIZER = "Cohere/Cohere-embed-multilingual-v3.0"

# Chunking settings
ENABLE_CHUNKING = True
MAX_CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

# Generation model
GEN_MODEL = "OCI"

# Retrieval and reranker settings
TOP_K = 3
TOP_N = 3
MAX_TOKENS = 1024
TEMPERATURE = 0.1

# Optional, better results when len(chunks_retrieved) > T
ADD_RERANKER = False
RERANKER_MODEL = "COHERE"
RERANKER_ID = ""

# Chat engine settings
CHAT_MODE = "condense_plus_context"
MEMORY_TOKEN_LIMIT = 3000

# Bits used to store embeddings
EMBEDDINGS_BITS = 64

# ID generation method
ID_GEN_METHOD = "HASH"

# Tracing settings
ADD_PHX_TRACING = False
PHX_PORT = "7777"
PHX_HOST = "0.0.0.0"

# Enable approximate query
LA2_ENABLE_INDEX = False

# UI settings
ADD_REFERENCES = True
LOGO_PATH = ""
