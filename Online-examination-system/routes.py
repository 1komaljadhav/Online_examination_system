from flask import Blueprint, render_template,request,flash,redirect,url_for
from models import Student,db,Questions,StudentAnswer,Evaluation,QuestionPaper,QuestionPaperQuestion
from utils import calculate_summary, save_evaluation_results, calculate_similarity, count_grammar_mistakes, word_count, load_model, load_dataset, load_tokenizer, evaluate_student_answers
import logging

main = Blueprint('main', __name__)


@main.route('/submit_marks', methods=['POST'])
def submit_marks():
    student_id = request.form.get('student_id')
    question_id = request.form.get('question_id')
    marks = request.form.get('marks')
    
    evaluation = Evaluation.query.filter_by(student_id=student_id, question_id=question_id).first()
    if evaluation:
        evaluation.predicted_marks = marks
    else:
        new_evaluation = Evaluation(
            student_id=student_id,
            question_id=question_id,
            similarity=0,
            grammar_mistakes=0,
            word_count=0,
            keywords=0,
            marks=marks
        )
        db.session.add(new_evaluation)
    
    db.session.commit()
    return redirect(url_for('main.view_answers', student_id=student_id))

@main.route('/evaluator_dashboard')
def evaluator_dashboard():
    students = Student.query.all()
    return render_template('evaluator_dashboard.html', students=students)

@main.route('/view_evaluation/<int:student_id>/<int:question_id>')
def view_evaluation(student_id, question_id):
    student = Student.query.get_or_404(student_id)
    question = Questions.query.get_or_404(question_id)
    answers = StudentAnswer.query.filter_by(student_id=student_id, question_id=question_id).all()
    return render_template('view_evaluation.html', student=student, question=question, answers=answers)

@main.route('/view_answers/<int:student_id>')
def view_answers(student_id):
    student = Student.query.get_or_404(student_id)
    answers = StudentAnswer.query.filter_by(student_id=student_id).all()
    evaluations = Evaluation.query.filter_by(student_id=student_id).all()
    
    # Debugging
    print(f'Student: {student.name}, ID: {student_id}, Answers: {len(answers)}, Evaluations: {len(evaluations)}')

    evaluations_dict = {e.question_id: e for e in evaluations}
    
    total_marks = sum(evaluations_dict.get(answer.question_id, Evaluation()).predicted_marks or 0 for answer in answers)
    
    return render_template(
        'view_answers.html',
        student=student,
        answers=answers,
        evaluations_dict=evaluations_dict,
        total_marks=total_marks,
        student_id=student_id  # Ensure this line is included

    )


@main.route('/calculate_totals', methods=['POST'])
def calculate_totals():
    students = Student.query.all()
    
    for student in students:
        evaluations = Evaluation.query.filter_by(student_id=student.id).all()
        if not evaluations:
            continue  # Skip if no evaluations found

        total_score = sum(evaluation.predicted_marks or 0 for evaluation in evaluations)
        
        # Debugging print
        print(f"Student ID: {student.id}, Total Score: {total_score}")

        # Update student's final score
        student.final_score = total_score
        db.session.commit()

    return redirect(url_for('main.evaluator_dashboard'))



@main.route('/')
def home():
    return render_template("home.html")
# Route to render the form for adding a question
@main.route('/add_question', methods=['GET', 'POST'])
def add_question():
    if request.method == 'POST':
        question_text = request.form['question_text']
        model_answer = request.form['model_answer']
        evaluator_id = 1  # Assuming logged-in evaluator with ID 1 for demo purposes

        # Create a new Question instance and save to the database
        new_question = Questions(question_text=question_text, model_answer=model_answer, created_by=evaluator_id)
        db.session.add(new_question)
        db.session.commit()
        flash('Question added successfully!', 'success')
        return redirect(url_for('main.add_question'))
    
    return render_template('add_question.html')
@main.route('/student_view_exam/<int:paper_id>/<int:student_id>', methods=['GET', 'POST'])
def student_view_exam(paper_id, student_id):
    # Get the student and question paper objects from the database
    student = Student.query.get_or_404(student_id)
    question_paper = QuestionPaper.query.get_or_404(paper_id)

    # Fetch the questions for the exam
    questions = Questions.query.join(
        QuestionPaperQuestion,
        Questions.id == QuestionPaperQuestion.question_id
    ).filter(
        QuestionPaperQuestion.question_paper_id == paper_id
    ).all()

    if request.method == 'POST':
        # Fetch the answers and question IDs from the form
        answers = {}
        for key, value in request.form.items():
            if key.startswith('answers_'):
                question_id = int(key.split('_')[1])  # Extract the question ID from the field name
                answers[question_id] = value

        # Now save the answers to the StudentAnswer table
        for question_id, answer_text in answers.items():
            new_answer = StudentAnswer(
                student_id=student_id,
                question_id=question_id,
                answer_text=answer_text
            )
            db.session.add(new_answer)
        
        db.session.commit()  # Commit all new answers to the database

        flash("Answers submitted successfully!", "success")
          # Redirect to some page after submission

    # Render the template with the necessary data if not POST (GET request)
    return render_template('student_view_exam.html', 
                           question_paper=question_paper, 
                           questions=questions, 
                           student=student, 
                           student_id=student_id)





@main.route('/student_dashboard/<int:student_id>')
def student_dashboard(student_id):
    # Get student information
    student = Student.query.filter_by(id=student_id).first()    
    print("Student Info:", student)  # Print student info
   # Get available exams for the student
    available_exams = QuestionPaper.query.all()
    print("Available Exams:", available_exams)  # Print available exams

    # Get student's exam results
    student_results =Student.query.filter_by(id=student_id).first()    
    print("Student Results:", student_results)  # Print student results

    return render_template('student_dashboard.html', 
                           student=student, 
                           available_exams=available_exams,
                           student_results=student_results)

@main.route('/start_exam', methods=['POST'])
def start_exam():
    student_id = request.form['student_id']
    exam_id = request.form['exam_id']
    
    # Logic to start the exam for the student
    return redirect(url_for('main.take_exam', exam_id=exam_id, student_id=student_id))







@main.route('/student_exam_dashboard', methods=['GET', 'POST'])
def student_exam_dashboard():
    student_id = 0
    error_message = None
    question_papers = []

    if request.method == 'POST':
        student_id = request.form['student_id'].strip()

        # Check if the student exists in the database
        student = Student.query.filter_by(id=student_id).first()
        print(student)
        if student:
            # If the student exists, fetch the available question papers
            question_papers = QuestionPaper.query.all()
        else:
            # If student doesn't exist, set an error message
            error_message = f"Student '{student_id}' not found in the system."

    return render_template('student_exam_dashboard.html', 
                           question_papers=question_papers, 
                           student_id=student_id,
                           error_message=error_message)

@main.route('/create_question_paper', methods=['GET', 'POST'])
def create_question_paper():
    if request.method == 'POST':
        paper_name = request.form['paper_name']
        selected_questions = request.form.getlist('questions')
        evaluator_id = 1  # Assuming logged-in evaluator with ID 1 for demo purposes

        # Create a new QuestionPaper instance and save to the database
        new_paper = QuestionPaper(paper_name=paper_name, evaluator_id=evaluator_id)
        db.session.add(new_paper)
        db.session.commit()  # Commit to get the new paper's ID

        # Debugging: Print selected questions to verify
        print(f"Selected questions: {selected_questions}")

        # Add selected questions to the question paper
        for question_id in selected_questions:
            question_id = int(question_id)  # Ensure it's an integer
            
            # Ensure question exists before adding it to the question paper
            question = Questions.query.get(question_id)
            if not question:
                flash(f"Question with id {question_id} does not exist", 'error')
                continue  # Skip to the next question if not found

            # Check if the question is already associated with the paper
            existing_association = QuestionPaperQuestion.query.filter_by(question_paper_id=new_paper.id, question_id=question_id).first()
            if not existing_association:
                paper_question = QuestionPaperQuestion(question_paper_id=new_paper.id, question_id=question_id)
                db.session.add(paper_question)
            else:
                flash(f"Question with id {question_id} is already added to this paper.", 'info')

        db.session.commit()  # Commit all additions at once
        flash("Question paper created successfully.", 'success')
        return redirect(url_for('main.create_question_paper'))

    # Fetch all available questions for the evaluator to choose from
    questions = Questions.query.all()
    flash("Question paper created successfully.", 'success')
        
    return render_template('create_paper.html', questions=questions)
    
def get_student_results(student_id):
    # Query to join StudentAnswer, Question, and Evaluation tables to fetch the required data
    results = db.session.query(StudentAnswer, Questions.question_text, Evaluation.predicted_marks)\
        .join(Questions, StudentAnswer.question_id == Questions.id)\
        .join(Evaluation, StudentAnswer.id == Evaluation.student_id)\
        .filter(StudentAnswer.student_id == student_id).all()
    
    # Fetch final score of the student from the Student table
    final_score = db.session.query(Student.final_score)\
        .filter(Student.id == student_id).first()
    
    return results, final_score

@main.route('/view_results/<int:student_id>')
def view_results(student_id):
    # Get student results and final score from the database
    student_results, final_score = get_student_results(student_id)

    # Debugging: Print the fetched results
    print(student_results)  # Check if this contains the expected results
    print(final_score)      # Check if final_score is being fetched correctly

    # Calculate total marks from the predicted marks
    total_marks = sum([result.predicted_marks for result in student_results])

    # Pass the results, total marks, and final score to the HTML template
    return render_template('student_results.html', 
                            student_id=student_id,   # Ensure student_id is passed to the template
                            results=student_results, 
                            total_marks=total_marks, 
                            final_score=final_score[0])


@main.route('/view_metrics/<int:student_id>/<int:question_id>', methods=['GET', 'POST'])
def view_metrics(student_id, question_id):
    answer_record = StudentAnswer.query.filter_by(student_id=student_id, question_id=question_id).first()
    question_record = Questions.query.filter_by(id=question_id).first()
    
    if not answer_record or not question_record:
        return "Answer or question not found", 404

    student_answer = answer_record.answer_text
    model_answer = question_record.model_answer

    try:
        # Load the model, tokenizer, and dataset
        model = load_model()
        tokenizer = load_tokenizer()
        ds = load_dataset()

        # Correctly call the calculate_summary function
        summary_result = calculate_summary(student_answer)
        logging.debug(f"Summary: {summary_result}")  # Debug log to check summary
        
        similarity_result = calculate_similarity(model_answer, student_answer)
        logging.debug(f"Similarity: {similarity_result}")  # Debug log to check similarity
        
        grammar_mistakes = count_grammar_mistakes(student_answer)
        word_count_result = word_count(student_answer)
        
        # Ensure that the evaluate_student_answers function returns the expected value
        marks = evaluate_student_answers(
                student_id=student_id,
                question_id=question_id,  # Pass the question_id
                model=model,
                tokenizer=tokenizer,
                max_seq_length=100,
                summary_result=summary_result,
                similarity_result=similarity_result,
                grammar_mistakes=grammar_mistakes,
                word_count_result=word_count_result
            )


    except Exception as e:
        logging.error(f"Error during evaluations: {e}")
        return "An error occurred during evaluation.", 500

    evaluation = {
        "similarity": similarity_result,
        "grammar_mistakes": grammar_mistakes,
        "word_count": word_count_result,
        "summary": summary_result,  # Ensure this variable is defined
        "predicted_marks": marks
    }
    if request.method == 'POST':
        # Update marks based on the form input
        new_marks = request.form.get('marks')
        
        if evaluation:
            evaluation.marks = new_marks  # Updating the marks in the evaluation
            db.session.commit()  # Save changes to the database
            flash('Marks updated successfully!', 'success')
        else:
            flash('No evaluation available to update.', 'warning')
        
    return render_template('after.html', answer=answer_record, evaluation=evaluation)
