"""
Python Version: 3.11

Description:
    This module provides the class to process, embed, store, and retrieve 
    documents info from Oracle 23ai.
"""

import logging
import re
import os
import shutil
from typing import List
from tqdm import tqdm
import array
import numpy as np
import time
import hashlib

from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
import oracledb
import ads

from tokenizers import Tokenizer
from ads.llm import GenerativeAIEmbeddings
from oci_utils import load_oci_config

from config import (
    EMBED_MODEL,
    TOKENIZER,
    EMBEDDINGS_BITS,
    ID_GEN_METHOD,
    ENABLE_CHUNKING,
    MAX_CHUNK_SIZE,
    CHUNK_OVERLAP,
    DB_USER,
    DB_PWD,
    DB_SERVICE,
    DB_HOST_IP,
    COMPARTMENT_OCID,
    ENDPOINT,
)

BATCH_SIZE = 40

def generate_id(nodes_list: List):
    """
    Generate IDs for the given list of nodes.

    Args:
        nodes_list (List): List of nodes.

    Returns:
        List: List of generated node IDs.
    """
    try:
        if ID_GEN_METHOD == "LLINDEX":
            nodes_ids = [doc.id_ for doc in nodes_list]
        elif ID_GEN_METHOD == "HASH":
            logging.info("Hashing to compute id...")
            nodes_ids = []
            for doc in tqdm(nodes_list):
                encoded_text = doc.text.encode()
                hash_object = hashlib.sha256(encoded_text)
                hash_hex = hash_object.hexdigest()
                nodes_ids.append(hash_hex)
        else:
            raise ValueError(f"Unknown ID_GEN_METHOD: {ID_GEN_METHOD}")
        return nodes_ids
    except Exception as e:
        logging.error(f"Error in generate_id: {e}")
        raise

def read_and_split_in_pages(input_files):
    """
    Read and split input files into pages.

    Args:
        input_files: List of input files.

    Returns:
        Tuple: Tuple containing lists of page texts, page IDs, and page numbers.
    """
    try:
        pages = SimpleDirectoryReader(input_files=input_files).load_data()
        logging.info(f"Read total {len(pages)} pages...")
        for doc in pages:
            doc.text = preprocess_text(doc.text)
        pages = remove_short_pages(pages, threshold=10)
        pages_text = [doc.text for doc in pages]
        pages_num = [doc.metadata["page_#"] for doc in pages]
        pages_id = generate_id(pages)
        return pages_text, pages_id, pages_num
    except Exception as e:
        logging.error(f"Error in read_and_split_in_pages: {e}")
        raise

def read_and_split_in_chunks(input_files):
    """
    Read and split input files into chunks.

    Args:
        input_files: List of input files.

    Returns:
        Tuple: Tuple containing lists of node texts, node IDs, and page numbers.
    """
    try:
        node_parser = SentenceSplitter(chunk_size=MAX_CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        pages = SimpleDirectoryReader(input_files=input_files).load_data()
        logging.info(f"Read total {len(pages)} pages...")
        for doc in pages:
            doc.text = preprocess_text(doc.text)
        pages = remove_short_pages(pages, threshold=10)
        nodes = node_parser.get_nodes_from_documents(pages, show_progress=True)
        nodes_text = [doc.text for doc in nodes]
        pages_num = [doc.metadata.get("page#", "unknown") for doc in nodes]
        nodes_id = generate_id(nodes)
        return nodes_text, nodes_id, pages_num
    except Exception as e:
        logging.error(f"Error in read_and_split_in_chunks: {e}")
        raise

def preprocess_text(text):
    """
    Preprocess the given text by removing unwanted characters and formatting.

    Args:
        text: The input text.

    Returns:
        str: The preprocessed text.
    """
    try:
        text = text.replace("\t", " ")
        text = text.replace(" -\n", "")
        text = text.replace("-\n", "")
        text = text.replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        return text
    except Exception as e:
        logging.error(f"Error in preprocess_text: {e}")
        raise

def remove_short_pages(pages, threshold):
    """
    Remove pages that are shorter than the specified word threshold.

    Args:
        pages: List of pages.
        threshold: Word count threshold.

    Returns:
        List: List of pages with sufficient length.
    """
    try:
        n_removed = 0
        for pag in pages:
            if len(pag.text.split(" ")) < threshold:
                pages.remove(pag)
                n_removed += 1
        logging.info(f"Removed {n_removed} short pages...")
        return pages
    except Exception as e:
        logging.error(f"Error in remove_short_pages: {e}")
        raise

def check_tokenization_length(tokenizer, batch):
    """
    Check the length of tokenized texts to ensure they do not exceed the maximum chunk size.

    Args:
        tokenizer: The tokenizer to use.
        batch: List of texts to tokenize.
    """
    try:
        for text in tqdm(batch):
            assert len(tokenizer.encode(text)) <= MAX_CHUNK_SIZE
        logging.info("Tokenization OK...")
    except Exception as e:
        logging.error(f"Error in check_tokenization_length: {e}")
        raise

def compute_embeddings(embed_model, nodes_text):
    """
    Compute embeddings for the given texts using the specified embedding model.

    Args:
        embed_model: The embedding model to use.
        nodes_text: List of texts to embed.

    Returns:
        List: List of computed embeddings.
    """
    try:
        cohere_tokenizer = Tokenizer.from_pretrained(TOKENIZER)
        embeddings = []
        for i in tqdm(range(0, len(nodes_text), BATCH_SIZE)):
            batch = nodes_text[i : i + BATCH_SIZE]
            embeddings_batch = embed_model.embed_documents(batch)
            embeddings.extend(embeddings_batch)
            print(f"Processed {i + len(batch)} of {len(nodes_text)} documents")
            time.sleep(0.1)  # Simulate some processing delay
            # Ensure stdout is flushed
            print(f"Batch {i // BATCH_SIZE + 1} embeddings computed", flush=True)
        return embeddings
    except Exception as e:
        logging.error(f"Error in compute_embeddings: {e}")
        raise

def save_embeddings_in_db(embeddings, pages_id, connection):
    """
    Save the provided embeddings to the Oracle database.

    Args:
        embeddings (list): List of embedding vectors.
        pages_id (list): List of page IDs corresponding to the embeddings.
        connection: The Oracle database connection.
    """
    tot_errors = 0
    try:
        with connection.cursor() as cursor:
            logging.info("Saving embeddings to DB...")
            for id, vector in zip(tqdm(pages_id), embeddings):
                array_type = "d" if EMBEDDINGS_BITS == 64 else "f"
                input_array = array.array(array_type, vector)
                try:
                    cursor.execute("INSERT INTO VECTORS VALUES (:1, :2)", [id, input_array])
                except Exception as e:
                    logging.error(f"Error in save_embeddings: {e}")
                    tot_errors += 1
        logging.info(f"Total errors in save_embeddings: {tot_errors}")
    except Exception as e:
        logging.error(f"Critical error in save_embeddings_in_db: {e}")
        raise

def save_chunks_in_db(pages_text, pages_id, pages_num, book_id, connection):
    """
    Save the provided text chunks to the Oracle database.

    Args:
        pages_text (list): List of text chunks.
        pages_id (list): List of page IDs.
        pages_num (list): List of page numbers.
        book_id: The book ID to associate with the text chunks.
        connection: The Oracle database connection.
    """
    tot_errors = 0
    try:
        with connection.cursor() as cursor:
            logging.info("Saving texts to DB...")
            cursor.setinputsizes(None, oracledb.DB_TYPE_CLOB)
            for id, text, page_num in zip(tqdm(pages_id), pages_text, pages_num):
                try:
                    cursor.execute(
                        "INSERT INTO CHUNKS (ID, CHUNK, PAGE_NUM, BOOK_ID) VALUES (:1, :2, :3, :4)",
                        [id, text, page_num, book_id],
                    )
                except Exception as e:
                    logging.error(f"Error in save_chunks: {e}")
                    tot_errors += 1
        logging.info(f"Total errors in save_chunks: {tot_errors}")
    except Exception as e:
        logging.error(f"Critical error in save_chunks_in_db: {e}")
        raise

def register_book(book_name, connection):
    """
    Register a book in the database.

    Args:
        book_name: The name of the book.
        connection: The Oracle database connection.

    Returns:
        int: The ID of the registered book.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT MAX(ID) FROM BOOKS")
            row = cursor.fetchone()
            new_key = row[0] + 1 if row[0] is not None else 1
        with connection.cursor() as cursor:
            query = "INSERT INTO BOOKS (ID, NAME) VALUES (:1, :2)"
            cursor.execute(query, [new_key, book_name])
        return new_key
    except Exception as e:
        logging.error(f"Error in register_book: {e}")
        raise

def get_files_from_directory(directory):
    """
    Get the list of files from the specified directory.

    Args:
        directory: The directory to list files from.

    Returns:
        List: List of file paths.
    """
    try:
        files = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        return files
    except Exception as e:
        logging.error(f"Error in get_files_from_directory: {e}")
        raise

def move_files(files, dest_directory):
    """
    Move the specified files to the destination directory.

    Args:
        files: List of file paths to move.
        dest_directory: The destination directory.
    """
    try:
        for file in files:
            shutil.move(file, dest_directory)
        logging.info(f"Moved {len(files)} files to {dest_directory}")
    except Exception as e:
        logging.error(f"Error in move_files: {e}")
        raise

def ensure_directories_exist(directories):
    """
    Ensure the specified directories exist, creating them if necessary.

    Args:
        directories: List of directory paths to check/create.
    """
    try:
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)
                logging.info(f"Created directory: {directory}")
    except Exception as e:
        logging.error(f"Error in ensure_directories_exist: {e}")
        raise

def main():
    """
    Main function to process, embed, store, and retrieve documents info from Oracle 23ai.
    """
    tot_pages = 0  # Initialize total pages at the beginning
    time_start = time.time()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    data_dir = os.path.join("data")
    unprocessed_dir = os.path.join(data_dir, "unprocessed")
    processed_dir = os.path.join(data_dir, "processed")

    ensure_directories_exist([data_dir, unprocessed_dir, processed_dir])

    try:
        files_to_process = get_files_from_directory(unprocessed_dir)
        if not files_to_process:
            raise Exception("Unprocessed directory is empty, there is nothing to process")

        print("\nStart processing...\n")
        print("List of books to be loaded and indexed:")
        for file in files_to_process:
            print(file)
        print("")

        oci_config = load_oci_config()
        api_keys_config = ads.auth.api_keys(oci_config)
        embed_model = GenerativeAIEmbeddings(
            compartment_id=COMPARTMENT_OCID,
            model=EMBED_MODEL,
            auth=api_keys_config,
            truncate="END",
            client_kwargs={"service_endpoint": ENDPOINT},
        )

        logging.info("Connecting to Oracle 23ai DB...")
        DSN = f"{DB_HOST_IP}/{DB_SERVICE}"

        with oracledb.connect(user=DB_USER, password=DB_PWD, dsn=DSN) as connection:
            logging.info("Successfully connected to Oracle 23ai Database...")

            num_pages = []
            for book in files_to_process:
                book_name = os.path.basename(book)
                logging.info(f"Processing book: {book_name}...")

                if not ENABLE_CHUNKING:
                    logging.info("Chunks are pages of the book...")
                    nodes_text, nodes_id, pages_num = read_and_split_in_pages([book])
                    num_pages.append(len(nodes_text))
                else:
                    logging.info(f"Enabled chunking, chunk_size: {MAX_CHUNK_SIZE}...")
                    nodes_text, nodes_id, pages_num = read_and_split_in_chunks([book])

                logging.info("Computing embeddings...")
                embeddings = compute_embeddings(embed_model, nodes_text)

                logging.info("Registering book...")
                book_id = register_book(book_name, connection)

                save_embeddings_in_db(embeddings, nodes_id, connection)
                logging.info("Save embeddings OK...")

                save_chunks_in_db(nodes_text, nodes_id, pages_num, book_id, connection)
                connection.commit()
                logging.info("Save texts OK...")

            tot_pages = np.sum(np.array(num_pages))
            if tot_pages is None or tot_pages == 0:
                tot_pages = 0
            move_files(files_to_process, processed_dir)
    except Exception as e:
        logging.error(f"Critical error in main: {e}")
        raise
    finally:
        time_elapsed = time.time() - time_start
        print("\nProcessing done !!!")
        print(f"We have processed {tot_pages} pages and saved text chunks and embeddings in the DB")
        print(f"Total elapsed time: {round(time_elapsed, 0)} sec.")
        print()

if __name__ == "__main__":
    main()