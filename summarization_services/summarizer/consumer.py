import pika
import json



from chunking import chunk_text
from summarization import summarize_text,summarize_final
from db.mongo import save_summary



RABBITMQ_HOST = "localhost"
RABBITMQ_QUEUE = "lecture_texts"


def callback(ch, method, properties, body):
    try:
        data = json.loads(body)

        lecture_id = data.get("lecture_id")
        text = data.get("text")

        if not lecture_id or not text:
            print("Invalid message:", data)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        print(f"Processing lecture {lecture_id}")

        # Chunk the text
        chunks = chunk_text(text)
        print(f" {len(chunks)} chunks created")

        # Summarize each chunk
        chunk_summaries = []

        for i, chunk in enumerate(chunks):
            # هدول ال 6 print بس نمحيهن مالهن داعي 
            print(f"Summarizing chunk {i + 1}/{len(chunks)}")
            print("\n" + "=" * 80)
            print(f"RAW CHUNK {i + 1}/{len(chunks)}")
            print("=" * 80)
            print(chunk)
            print("=" * 80)
            summary = summarize_text(chunk)

            if summary:
                chunk_summaries.append(summary)

        if not chunk_summaries:
            print("No summaries generated")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Combine summaries
        # Combine partial summaries
        cleaned_summaries = []

        for summary in chunk_summaries:
            cleaned = summary.replace(
                "**Summary in Arabic:**",
                ""
            ).strip()

            cleaned = cleaned.replace(
                "**Summary in English:**",
                ""
            ).strip()

            if cleaned:
                cleaned_summaries.append(cleaned)
        #  بدنا نطبع الـ partial summaries قبل Stage 2 يعني بس نخلص نمحيها لعند هي print("-" * 80)

        print("\n" + "=" * 80)
        print("PARTIAL SUMMARIES")
        print("=" * 80)

        for i, summary in enumerate(cleaned_summaries, start=1):
            print(f"\n--- PARTIAL SUMMARY {i} ---")
            print(summary)
            print("-" * 80)


        combined_summaries = "\n\n".join(cleaned_summaries)

        print(
            f"Creating final summary from "
            f"{len(cleaned_summaries)} partial summaries"
        )

        # Create ONE coherent final summary
        final_summary = summarize_final(
            combined_summaries
        )

        if not final_summary:
            print("Final summarization failed")
            return

        # Save to MongoDB
        save_summary(lecture_id, final_summary)

        print(f"Summary saved for lecture {lecture_id}")

        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print("Consumer error:", str(e))
        # Do NOT ack → RabbitMQ will retry


def start_consumer():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )
    channel = connection.channel()

    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=RABBITMQ_QUEUE,
        on_message_callback=callback
    )

    print("Waiting for lecture messages...")
    channel.start_consuming()


if __name__ == "__main__":
    start_consumer()