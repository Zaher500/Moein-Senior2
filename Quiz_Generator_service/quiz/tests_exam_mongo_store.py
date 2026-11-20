
import uuid
from unittest.mock import patch

from bson import BSON
from django.test import SimpleTestCase

from quiz.services.mongo_store import store_llm_response


class ExamMongoStoreTests(SimpleTestCase):

    @patch("quiz.services.mongo_store.MongoClient")
    def test_multi_lecture_exam_log_is_bson_compatible(
        self,
        mock_mongo_client,
    ):
        quiz_id = uuid.uuid4()
        student_id = uuid.uuid4()
        lecture_ids = [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        ]

        raw_responses = {
            lecture_ids[0]: "First lecture LLM response",
            lecture_ids[1]: "Second lecture LLM response",
        }

        questions = [
            {
                "question_type": "TRUE_FALSE",
                "question_text": "Example question",
                "correct_answer": "True",
                "source_lecture_id": lecture_ids[0],
            }
        ]

        store_llm_response(
            quiz_id=quiz_id,
            lecture_id=None,
            student_id=student_id,
            raw_response=raw_responses,
            parsed_questions=questions,
        )

        client = mock_mongo_client.return_value

        collection = (
            client.__getitem__.return_value
            .__getitem__.return_value
        )

        collection.insert_one.assert_called_once()

        document = collection.insert_one.call_args.args[0]

        self.assertEqual(document["quiz_id"], str(quiz_id))
        self.assertEqual(document["student_id"], str(student_id))
        self.assertIsNone(document["lecture_id"])

        self.assertEqual(
            document["raw_llm_response"],
            raw_responses,
        )

        self.assertEqual(
            document["parsed_questions"],
            questions,
        )

        # Verify MongoDB can encode the document.
        encoded = BSON.encode(document)
        decoded = BSON(encoded).decode()

        self.assertEqual(
            decoded["raw_llm_response"],
            raw_responses,
        )

        client.close.assert_called_once()
