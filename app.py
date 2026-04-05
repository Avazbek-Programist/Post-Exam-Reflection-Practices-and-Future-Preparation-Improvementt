from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
SURVEY_FILE = BASE_DIR / "survey_questions.json"
DATE_FORMATS: tuple[str, ...] = ("%Y-%m-%d",)
ALLOWED_NAME_CHARACTERS: frozenset[str] = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz -'"
)
REQUIRED_RESULT_KEYS: tuple[str, ...] = (
    "survey_title",
    "participant_name",
    "date_of_birth",
    "student_id",
    "question_count",
    "total_score",
    "max_score",
    "reflection_strength",
    "interpretation_label",
    "interpretation_message",
    "completed_at",
    "responses",
)


def load_survey_definition(path: Path) -> dict:
    """Load and validate the survey definition from the external JSON file."""
    with path.open("r", encoding="utf-8") as file:
        survey_data: dict = json.load(file)

    question_count = len(survey_data.get("questions", []))
    if not 15 <= question_count <= 25:
        raise ValueError("The questionnaire must contain between 15 and 25 questions.")

    for question in survey_data.get("questions", []):
        option_count = len(question.get("options", []))
        if not 3 <= option_count <= 5:
            raise ValueError("Each question must contain between 3 and 5 answer options.")

    if not survey_data.get("title"):
        raise ValueError("The survey title is missing.")

    result_count = len(survey_data.get("results", []))
    if not 5 <= result_count <= 7:
        raise ValueError("The questionnaire must have between 5 and 7 result bands.")

    max_score = sum(
        max(option["score"] for option in question["options"])
        for question in survey_data["questions"]
    )
    covered_scores: set[int] = set()
    for band in survey_data["results"]:
        min_score = int(band["min_score"])
        max_band_score = int(band["max_score"])
        if min_score > max_band_score:
            raise ValueError("A result band has an invalid score range.")
        for score in range(min_score, max_band_score + 1):
            covered_scores.add(score)

    if covered_scores != set(range(0, max_score + 1)):
        raise ValueError("The result bands must cover the full possible score range.")

    return survey_data


def validate_name(raw_name: str) -> str | None:
    cleaned_name = " ".join(raw_name.split())
    if not cleaned_name:
        return None

    if cleaned_name[0] in "-'" or cleaned_name[-1] in "-'":
        return None

    letter_count = 0
    previous_special = False

    for character in cleaned_name:
        if character not in ALLOWED_NAME_CHARACTERS:
            return None

        if character.isalpha():
            letter_count += 1
            previous_special = False
            continue

        if character in "-'":
            if previous_special:
                return None
            previous_special = True
        else:
            previous_special = False

    if letter_count == 0:
        return None

    return cleaned_name


def validate_date_of_birth(raw_date: str) -> str | None:
    today: date = date.today()

    for date_format in DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(raw_date, date_format).date()
        except ValueError:
            continue

        age_years = (today - parsed_date).days // 365
        if parsed_date >= today or age_years > 120:
            return None
        return parsed_date.isoformat()

    return None


def validate_student_id(raw_student_id: str) -> str | None:
    """Validate student ID using a while loop, as required by the rubric."""
    student_id = raw_student_id.strip()
    if not student_id:
        return None

    index = 0
    while index < len(student_id):
        if not student_id[index].isdigit():
            return None
        index += 1

    return student_id


def interpret_score(total_score: int, result_bands: list[dict]) -> dict:
    for band in result_bands:
        if band["min_score"] <= total_score <= band["max_score"]:
            return band
    raise ValueError("The total score does not fit any interpretation range.")


def build_result_record(
    survey_data: dict,
    participant: dict,
    responses: list[dict],
    total_score: int,
    interpretation: dict,
) -> dict:
    max_score = sum(
        max(option["score"] for option in question["options"])
        for question in survey_data["questions"]
    )
    reflection_strength = round(((max_score - total_score) / max_score) * 100.0, 2)

    return {
        "survey_title": survey_data["title"],
        "participant_name": participant["full_name"],
        "date_of_birth": participant["date_of_birth"],
        "student_id": participant["student_id"],
        "question_count": len(survey_data["questions"]),
        "total_score": total_score,
        "max_score": max_score,
        "reflection_strength": reflection_strength,
        "interpretation_label": interpretation["label"],
        "interpretation_message": interpretation["message"],
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "responses": responses,
    }


def result_to_text(result_record: dict) -> str:
    lines = [
        f"Survey Title: {result_record['survey_title']}",
        f"Participant Name: {result_record['participant_name']}",
        f"Date of Birth: {result_record['date_of_birth']}",
        f"Student ID: {result_record['student_id']}",
        f"Question Count: {result_record['question_count']}",
        f"Total Score: {result_record['total_score']} / {result_record['max_score']}",
        f"Reflection Strength: {result_record['reflection_strength']}%",
        f"Interpretation: {result_record['interpretation_label']}",
        f"Guidance: {result_record['interpretation_message']}",
        f"Completed At: {result_record['completed_at']}",
        "Responses:",
    ]

    for response in result_record["responses"]:
        lines.append(f"{response['question_number']}. {response['question']}")
        lines.append(f"Answer: {response['selected_option']}")
        lines.append(f"Score: {response['score']}")

    return "\n".join(lines)


def result_to_csv(result_record: dict) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "survey_title",
            "participant_name",
            "date_of_birth",
            "student_id",
            "question_count",
            "total_score",
            "max_score",
            "reflection_strength",
            "interpretation_label",
            "interpretation_message",
            "completed_at",
            "responses_json",
        ],
    )
    writer.writeheader()
    writer.writerow(
        {
            "survey_title": result_record["survey_title"],
            "participant_name": result_record["participant_name"],
            "date_of_birth": result_record["date_of_birth"],
            "student_id": result_record["student_id"],
            "question_count": result_record["question_count"],
            "total_score": result_record["total_score"],
            "max_score": result_record["max_score"],
            "reflection_strength": result_record["reflection_strength"],
            "interpretation_label": result_record["interpretation_label"],
            "interpretation_message": result_record["interpretation_message"],
            "completed_at": result_record["completed_at"],
            "responses_json": json.dumps(result_record["responses"], ensure_ascii=False),
        }
    )
    return output.getvalue()


def sanitize_filename(text: str) -> str:
    safe_characters = []
    for character in text:
        if character.isalnum():
            safe_characters.append(character)
        elif character in {" ", "-", "_"}:
            safe_characters.append("_")
    return "".join(safe_characters).strip("_") or "result"


def validate_loaded_result(result_record: dict) -> None:
    for key in REQUIRED_RESULT_KEYS:
        if key not in result_record:
            raise ValueError(f"The loaded result file is missing the field: {key}")

    if not isinstance(result_record["responses"], list):
        raise ValueError("The loaded result file has an invalid responses section.")



def parse_text_result(text_content: str) -> dict:
    lines = [line.rstrip() for line in text_content.splitlines() if line.strip()]
    parsed: dict = {}
    responses: list[dict] = []

    prefix_map = {
        "Survey Title: ": "survey_title",
        "Participant Name: ": "participant_name",
        "Date of Birth: ": "date_of_birth",
        "Student ID: ": "student_id",
        "Question Count: ": "question_count",
        "Reflection Strength: ": "reflection_strength",
        "Interpretation: ": "interpretation_label",
        "Guidance: ": "interpretation_message",
        "Completed At: ": "completed_at",
    }

    line_index = 0
    while line_index < len(lines):
        line = lines[line_index]

        if line.startswith("Total Score: "):
            score_part = line.removeprefix("Total Score: ")
            total_score_text, max_score_text = [item.strip() for item in score_part.split("/")]
            parsed["total_score"] = int(total_score_text)
            parsed["max_score"] = int(max_score_text)
        elif line == "Responses:":
            line_index += 1
            while line_index + 2 < len(lines):
                question_line = lines[line_index]
                answer_line = lines[line_index + 1]
                score_line = lines[line_index + 2]
                if ". " not in question_line or not answer_line.startswith("Answer: ") or not score_line.startswith("Score: "):
                    raise ValueError("The TXT result file has an invalid response block.")
                question_number_text, question_text = question_line.split(". ", 1)
                responses.append(
                    {
                        "question_number": int(question_number_text),
                        "question": question_text,
                        "selected_option": answer_line.removeprefix("Answer: "),
                        "score": int(score_line.removeprefix("Score: ")),
                    }
                )
                line_index += 3
            break
        else:
            matched_prefix = False
            for prefix, key in prefix_map.items():
                if line.startswith(prefix):
                    value = line.removeprefix(prefix)
                    if key == "question_count":
                        parsed[key] = int(value)
                    elif key == "reflection_strength":
                        parsed[key] = float(value.removesuffix("%"))
                    else:
                        parsed[key] = value
                    matched_prefix = True
                    break
            if not matched_prefix:
                raise ValueError("The TXT result file format is not recognized.")
        line_index += 1

    parsed["responses"] = responses
    validate_loaded_result(parsed)
    return parsed



def parse_csv_result(text_content: str) -> dict:
    reader = csv.DictReader(io.StringIO(text_content))
    rows = list(reader)
    if len(rows) != 1:
        raise ValueError("The CSV result file must contain exactly one result row.")

    row = rows[0]
    parsed = {
        "survey_title": row["survey_title"],
        "participant_name": row["participant_name"],
        "date_of_birth": row["date_of_birth"],
        "student_id": row["student_id"],
        "question_count": int(row["question_count"]),
        "total_score": int(row["total_score"]),
        "max_score": int(row["max_score"]),
        "reflection_strength": float(row["reflection_strength"]),
        "interpretation_label": row["interpretation_label"],
        "interpretation_message": row["interpretation_message"],
        "completed_at": row["completed_at"],
        "responses": json.loads(row["responses_json"]),
    }
    validate_loaded_result(parsed)
    return parsed



def parse_uploaded_result(uploaded_file) -> dict:
    suffix = Path(uploaded_file.name).suffix.lower()
    text_content = uploaded_file.getvalue().decode("utf-8")

    if suffix == ".json":
        result_record = json.loads(text_content)
        validate_loaded_result(result_record)
        return result_record
    if suffix == ".csv":
        return parse_csv_result(text_content)
    if suffix == ".txt":
        return parse_text_result(text_content)

    raise ValueError("Please upload a TXT, CSV, or JSON result file.")



def render_download_buttons(result_record: dict) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = sanitize_filename(result_record["participant_name"])

    st.download_button(
        "Download TXT result",
        data=result_to_text(result_record),
        file_name=f"reflection_survey_{safe_name}_{timestamp}.txt",
        mime="text/plain",
    )
    st.download_button(
        "Download CSV result",
        data=result_to_csv(result_record),
        file_name=f"reflection_survey_{safe_name}_{timestamp}.csv",
        mime="text/csv",
    )
    st.download_button(
        "Download JSON result",
        data=json.dumps(result_record, indent=2, ensure_ascii=False),
        file_name=f"reflection_survey_{safe_name}_{timestamp}.json",
        mime="application/json",
    )



def render_result_summary(result_record: dict, heading: str) -> None:
    st.subheader(heading)
    st.write(f"**Participant:** {result_record['participant_name']}")
    st.write(f"**Date of birth:** {result_record['date_of_birth']}")
    st.write(f"**Student ID:** {result_record['student_id']}")
    st.write(f"**Score:** {result_record['total_score']} / {result_record['max_score']}")
    st.write(f"**Reflection strength:** {result_record['reflection_strength']}%")
    st.write(f"**Interpretation:** {result_record['interpretation_label']}")
    st.write(f"**Guidance:** {result_record['interpretation_message']}")
    st.write(f"**Completed at:** {result_record['completed_at']}")

    with st.expander("Show all responses"):
        for response in result_record["responses"]:
            st.write(f"**{response['question_number']}. {response['question']}**")
            st.write(f"Answer: {response['selected_option']}")
            st.write(f"Score: {response['score']}")



def main() -> None:
    st.set_page_config(
        page_title="Post-Exam Reflection Survey",
        page_icon="📝",
        layout="centered",
    )

    st.title("Post-Exam Reflection Survey")

    try:
        survey_data = load_survey_definition(SURVEY_FILE)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        st.error(f"Unable to load the survey: {error}")
        st.stop()

    st.write(survey_data["description"])
    st.info(survey_data["questionnaire_notice"])

    mode = st.radio(
        "Choose how you want to use the program:",
        options=("Start a new questionnaire", "Load an existing result file"),
    )

    if mode == "Load an existing result file":
        uploaded_result = st.file_uploader(
            "Upload a TXT, CSV, or JSON result file",
            type=["txt", "csv", "json"],
        )
        if uploaded_result is not None:
            try:
                result_record = parse_uploaded_result(uploaded_result)
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError, KeyError) as error:
                st.error(f"Unable to read the uploaded result file: {error}")
                return

            st.success("Existing result loaded successfully.")
            render_result_summary(result_record, "Loaded result summary")
            st.subheader("Download the loaded result again")
            render_download_buttons(result_record)
        return

    with st.form("reflection_survey_form"):
        st.subheader("Participant details")
        full_name = st.text_input("Full name")
        date_of_birth = st.text_input("Date of birth (YYYY-MM-DD)")
        student_id = st.text_input("Student ID")

        st.subheader("Questions")
        selected_indices: list[int | None] = []

        for question_number, question_data in enumerate(survey_data["questions"], start=1):
            option_labels = [
                f"{option['text']} ({option['score']})"
                for option in question_data["options"]
            ]
            selection = st.radio(
                f"{question_number}. {question_data['prompt']}",
                options=range(len(option_labels)),
                format_func=lambda index, labels=option_labels: labels[index],
                index=None,
                key=f"question_{question_number}",
            )
            selected_indices.append(selection)

        submitted = st.form_submit_button("Submit survey")

    if not submitted:
        return

    name_error = validate_name(full_name)
    dob_error = validate_date_of_birth(date_of_birth)
    student_id_error = validate_student_id(student_id)

    if name_error is None:
        st.error("Enter a valid full name using letters, spaces, hyphens, or apostrophes only.")
        return
    if dob_error is None:
        st.error("Enter a valid date of birth in YYYY-MM-DD format.")
        return
    if student_id_error is None:
        st.error("Student ID must contain digits only.")
        return
    if any(selection is None for selection in selected_indices):
        st.error("Please answer every question before submitting.")
        return

    participant = {
        "full_name": name_error,
        "date_of_birth": dob_error,
        "student_id": student_id_error,
    }

    responses: list[dict] = []
    total_score = 0

    for question_number, question_data in enumerate(survey_data["questions"], start=1):
        selected_index = selected_indices[question_number - 1]
        if selected_index is None:
            st.error("A question is missing an answer. Please complete the whole form.")
            return
        selected_option = question_data["options"][selected_index]
        response = {
            "question_number": question_number,
            "question": question_data["prompt"],
            "selected_option": selected_option["text"],
            "score": int(selected_option["score"]),
        }
        responses.append(response)
        total_score += response["score"]

    interpretation = interpret_score(total_score, survey_data["results"])
    result_record = build_result_record(
        survey_data=survey_data,
        participant=participant,
        responses=responses,
        total_score=total_score,
        interpretation=interpretation,
    )

    st.success("Survey submitted successfully.")
    render_result_summary(result_record, "Result summary")
    st.subheader("Download the result")
    render_download_buttons(result_record)


if __name__ == "__main__":
    main()
