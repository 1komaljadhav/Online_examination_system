import subprocess
import logging
import re
from collections import Counter
from nltk.tokenize import sent_tokenize
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import language_tool_python
import pandas as pd
import pickle
import nltk
import spacy
from tensorflow.keras.preprocessing.sequence import pad_sequences
from transformers import pipeline
from models import StudentAnswer, Questions, db ,Evaluation
       
sentence_model = SentenceTransformer('distilbert-base-nli-stsb-mean-tokens')
tool = language_tool_python.LanguageTool('en-US')
from models import Evaluation  # Import the Evaluation model

def save_evaluation_results(student_id, question_id, summary, similarity, grammar_mistakes, word_count, predicted_marks):
    try:
        predicted_marks = float(predicted_marks)
        evaluation = Evaluation(
            student_id=student_id,
            question_id=question_id,
            summary=summary,
            similarity=similarity,
            grammar_mistakes=grammar_mistakes,
            word_count=word_count,
            predicted_marks=predicted_marks
        )
        db.session.add(evaluation)
        db.session.commit()
        logging.info("Evaluation results saved successfully.")
    except Exception as e:
        db.session.rollback()  # Add rollback here
        logging.error(f"Error saving evaluation results: {e}")

def load_dataset(dataset_path='student_evaluation_results (2).csv'):
    df = pd.read_csv(dataset_path, encoding='ISO-8859-1')
    logging.info("Dataset loaded successfully.")
    return df

def load_model(model_path='answer_evaluation_model.pkl'):
    model = pickle.load(open(model_path, 'rb'))
    logging.info("Model loaded successfully.")
    return model

def load_tokenizer(tokenizer_path='tokenizer.pkl'):
    tokenizer = pickle.load(open(tokenizer_path, 'rb'))
    logging.info("Tokenizer loaded successfully.")
    return tokenizer
def evaluate_student_answers(student_id, question_id, model, tokenizer, max_seq_length, summary_result, similarity_result, grammar_mistakes, word_count_result):
    student_answers_data = StudentAnswer.query.filter_by(student_id=student_id).all()
    if not student_answers_data:
        return "No answers found for the given student ID"

    logging.debug(f"Number of answers fetched: {len(student_answers_data)}")

    questions = []
    student_answers = []

    for i, answer_data in enumerate(student_answers_data):
        question = str(answer_data.question_id)
        answer = answer_data.answer_text

        logging.debug(f"Question {i+1}: {question}")
        logging.debug(f"Answer {i+1}: {answer}")

        questions.append(question)
        student_answers.append(answer)

    question_seqs = tokenizer.texts_to_sequences(questions)
    answer_seqs = tokenizer.texts_to_sequences(student_answers)

    question_seqs = pad_sequences(question_seqs, maxlen=max_seq_length)
    answer_seqs = pad_sequences(answer_seqs, maxlen=max_seq_length)

    logging.debug(f"Question Sequences Shape: {question_seqs.shape}")
    logging.debug(f"Answer Sequences Shape: {answer_seqs.shape}")

    predicted_marks = model.predict([question_seqs, answer_seqs])
    predicted_marks = float(predicted_marks[0][0])
    predicted_marks = round(predicted_marks, 2)
    
    logging.debug(f"Predicted Marks: {predicted_marks}")
    
    save_evaluation_results(
        student_id=student_id,
        question_id=question_id,
        summary=summary_result,
        similarity=similarity_result,
        grammar_mistakes=grammar_mistakes,
        word_count=word_count_result,
        predicted_marks=predicted_marks
    )

    return f"{predicted_marks}"

def check_syntax_errors(c_code):
    try:
        with open("temp.c", "w") as f:
            f.write(c_code)
        
        result = subprocess.run(
            ["gcc", "-fsyntax-only", "temp.c"], 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        return result.stderr.decode('utf-8') if result.returncode != 0 else "No syntax errors detected."
    except Exception as e:
        logging.error(f"Error checking syntax: {e}")
        return "Error checking syntax."

def calculate_total_marks(predictions, max_marks_per_question):
    try:
        total_marks = sum(predictions)  # Assuming the model outputs a single value per answer
        return total_marks
    except Exception as e:
        logging.error(f"Error calculating total marks: {e}")
        return 0
from transformers import pipeline
import logging

from transformers import pipeline
import logging

def calculate_summary(text, max_length=50, min_length=20, length_penalty=2.0, num_beams=4, no_repeat_ngram_size=2):
    try:
        summarizer = pipeline('summarization', model='facebook/bart-large-cnn')
        # Adjust max_length if input text is shorter
        max_length = min(max_length, len(text))
        summary = summarizer(text, max_length=max_length, min_length=min_length, 
                             length_penalty=length_penalty, num_beams=num_beams, 
                             no_repeat_ngram_size=no_repeat_ngram_size)
        return summary[0]['summary_text']
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return "Error generating summary."

def calculate_similarity(model_answer, student_answer):
    
    logging.debug(f"Model Answer: {model_answer}")
    logging.debug(f"Student Answer: {student_answer}")
    
    if model_answer is None or student_answer is None:
        logging.error("One or both input answers are None.")
        return 0.0
    
    try:
        enc_model = sentence_model.encode(model_answer)
        enc_student = sentence_model.encode(student_answer)
        cos_sim = cosine_similarity([enc_model], [enc_student])
        similarity_score = cos_sim[0][0] * 100  # Convert to percentage
        return round(similarity_score, 2)
    except Exception as e:
        logging.error(f"Error calculating similarity: {e}")
        return 0.0

def count_grammar_mistakes(text):
    try:
        matches = tool.check(text)
        return len(matches)
    except Exception as e:
        logging.error(f"Error counting grammar mistakes: {e}")
        return 0

def word_count(text):
    try:
        return len(text.split())
    except Exception as e:
        logging.error(f"Error calculating word count: {e}")
        return 0
