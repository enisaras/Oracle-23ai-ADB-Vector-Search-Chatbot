"""
Python Version: 3.11

Description:
    This module provides UI for Oracle 23ai based chatbot to communicate with documents.
"""

import os
import time
import logging
import subprocess
import streamlit as st
from pathlib import Path
import chat_engine
from config import ADD_REFERENCES, STREAM_CHAT, VERBOSE

# Set the configuration for the Streamlit app
st.set_page_config(page_title="Oracle 23ai Vector Search Assistant", layout="wide")

# Initialize directories for file uploads and processed files
upload_dir = Path("data/unprocessed")
processed_dir = Path("data/processed")
upload_dir.mkdir(parents=True, exist_ok=True)
processed_dir.mkdir(parents=True, exist_ok=True)

# Title for the sidebar
st.markdown("<h1 style='text-align: center;'>Oracle 23ai Vector Search Assistant</h1>", unsafe_allow_html=True)

# Cache the chat engine creation to improve performance
@st.cache_resource
def create_chat_engine():
    return chat_engine.create_chat_engine(
        verbose=VERBOSE,
        **{key: st.session_state[key] for key in ["top_k", "max_tokens", "temperature", "top_n"]}
    )

# Function to reset the conversation state
def reset_conversation():
    st.session_state.messages = []
    st.session_state.chat_engine, st.session_state.token_counter = create_chat_engine()
    st.session_state.chat_engine.reset()
    st.session_state.question_count = 0

# Initialize default session state values if they don't exist
if "max_tokens" not in st.session_state:
    st.session_state.max_tokens = 1024
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.5
if "top_k" not in st.session_state:
    st.session_state.top_k = 3
if "top_n" not in st.session_state:
    st.session_state.top_n = 3

# Streamlit sidebar form for adjusting model parameters
with st.sidebar.form(key="input-form"):
    max_tokens = st.number_input('Maximum Tokens', min_value=512, max_value=1024, value=st.session_state.max_tokens)
    temperature = st.number_input('Temperature', min_value=0.0, max_value=1.0, value=st.session_state.temperature, step=0.1)
    top_k = st.slider("TOP_K", 1, 10, value=st.session_state.top_k)
    top_n = st.slider("TOP_N", 1, 10, value=st.session_state.top_n)
    submitted_sidebar = st.form_submit_button("Submit", type="primary", on_click=reset_conversation, use_container_width=True)

# Update session state values if the form is submitted
if submitted_sidebar:
    st.session_state.update({
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_k": top_k,
        "top_n": top_n
    })

# Function to save uploaded files to the specified directory
def save_uploaded_file(uploaded_file, upload_dir):
    file_path = upload_dir / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

# Streamlit sidebar form for file upload
with st.sidebar.form(key="file-uploader-form", clear_on_submit=True):
    file = st.file_uploader("Document Uploader", accept_multiple_files=True, type=['txt', 'csv', 'pdf', 'docx'], label_visibility="collapsed")
    submitted = st.form_submit_button("Upload", type="primary", use_container_width=True)

# Handle file upload and processing
if submitted and file:
    if not isinstance(file, list):
        file = [file]
    logging.info("Uploading file")
    uploaded_file_paths = []
    for uploaded_file in file:
        processed_file_path = Path(processed_dir) / uploaded_file.name
        if processed_file_path.exists():
            st.error(f"Document {uploaded_file.name} already processed. Please try another document or begin asking questions.")
        else:
            file_path = save_uploaded_file(uploaded_file, Path(upload_dir))
            uploaded_file_paths.append(file_path)
            logging.info(f"Uploaded document: {uploaded_file.name}")

    # Process the uploaded files
    if uploaded_file_paths:
        progress_bar = st.progress(0)
        progress_text = st.empty()

        try:
            with st.spinner(f"Processing document {uploaded_file.name}..."):
                logging.info("Document processing started..")
                process = subprocess.Popen(
                    ["python", "process_documents.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )

                total_steps = 100  # Adjust this based on your script's output
                current_step = 0

                # Monitor the progress of the subprocess
                while process.poll() is None:
                    output = process.stdout.readline()
                    if output:
                        current_step += 1  # Adjust based on actual progress parsing logic
                        progress_percentage = min(current_step / total_steps, 1.0)
                        progress_bar.progress(progress_percentage)
                        progress_text.text(output.strip())
                        time.sleep(0.1)  # Simulate some processing delay

                # Ensure any remaining output is processed
                for output in process.stdout:
                    if output:
                        current_step += 1  # Adjust based on actual progress parsing logic
                        progress_percentage = min(current_step / total_steps, 1.0)
                        progress_bar.progress(progress_percentage)
                        progress_text.text(output.strip())
                        time.sleep(0.1)
    
                stdout, stderr = process.communicate()
                return_code = process.returncode
                if return_code == 0:
                    progress_bar.progress(1.0)  # Ensure the progress bar completes
                    progress_text.text("Assistant is now ready to answer questions.")
                else:
                    st.error(f"Document processing failed with return code {return_code}")
                    st.error(stderr)

        except subprocess.CalledProcessError as e:
            st.error(f"An error occurred while processing the document: {e}")

# Display chat messages in the Streamlit app
def display_chat_messages():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Function to handle non-streaming output
def no_stream_output(response):
    output = response.response
    if ADD_REFERENCES and len(response.source_nodes) > 0:
        output += "\n\n Ref.:\n\n"
        for node in response.source_nodes:
            output += str(node.metadata).replace("{", "").replace("}", "") + "  \n"
    st.markdown(output)
    return output

# Function to handle streaming output
def stream_output(response):
    text_placeholder = st.empty()
    output = ""
    for text in response.response_gen:
        output += text
        text_placeholder.markdown(output, unsafe_allow_html=True)
    if ADD_REFERENCES:
        output += "\n\n Ref.:\n\n"
        for node in response.source_nodes:
            output += str(node.metadata).replace("{", "").replace("}", "") + "  \n"
        text_placeholder.markdown(output, unsafe_allow_html=True)
    return output

# Main function to run the Streamlit app
def main():
    _, c1 = st.columns([5, 1])
    c1.button("Clear Chat History", type="primary", on_click=reset_conversation)

    # Configure logging
    logger = logging.getLogger("ConsoleLogger")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.propagate = False

    # Initialize session state if not already done
    if "messages" not in st.session_state:
        reset_conversation()

    with st.spinner("Initializing RAG chain..."):
        st.session_state.chat_engine, st.session_state.token_counter = create_chat_engine()

    display_chat_messages()

    # Input for the user question
    question = st.chat_input("Hello, how can I help you?")
    if question:
        st.chat_message("user").markdown(question)
        st.session_state.messages.append({"role": "user", "content": question})

        try:
            logger.info("Calling RAG chain..")
            logger.info(f"top_k= {st.session_state.top_k}, max_tokens= {st.session_state.max_tokens}, temperature= {st.session_state.temperature}, top_n= {st.session_state.top_n}")

            with st.spinner("Waiting..."):
                time_start = time.time()
                st.session_state.question_count += 1
                logger.info("")
                logger.info(f"Question no. {st.session_state.question_count} is {question}")

                # Generate response using the chat engine
                if STREAM_CHAT:
                    response = st.session_state.chat_engine.stream_chat(question)
                else:
                    response = st.session_state.chat_engine.chat(question)

                time_elapsed = time.time() - time_start
                logger.info(f"Elapsed time: {round(time_elapsed, 1)} sec.")

                str_token1 = f"LLM Prompt Tokens: {st.session_state.token_counter.prompt_llm_token_count}"
                str_token2 = f"LLM Completion Tokens: {st.session_state.token_counter.completion_llm_token_count}"
                logger.info(str_token1)
                logger.info(str_token2)

                # Display response from the assistant
                with st.chat_message("assistant"):
                    if STREAM_CHAT:
                        output = stream_output(response)
                    else:
                        output = no_stream_output(response)

                st.session_state.messages.append({"role": "assistant", "content": output})

        except Exception as e:
            logger.error("An error occurred: " + str(e))
            st.error("An error occurred: " + str(e))

# Entry point for the script
if __name__ == "__main__":
    main()