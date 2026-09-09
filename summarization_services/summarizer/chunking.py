def chunk_text(text, chunk_size=1200):
    """
    Chunk text by paragraphs first, then by size.
    Preserves lists and sentences.
    chunk_size is approximate word count.
    """

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = []
    current_length = 0

    for para in paragraphs:
        words = para.split()
        para_len = len(words)

        # If paragraph alone is too big, split it safely
        if para_len > chunk_size:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0

            # Split large paragraph by sentences
            sentences = para.split(". ")
            temp = []
            temp_len = 0

            for sentence in sentences:
                sentence_words = sentence.split()
                if temp_len + len(sentence_words) <= chunk_size:
                    temp.append(sentence)
                    temp_len += len(sentence_words)
                else:
                    chunks.append(". ".join(temp).strip())
                    temp = [sentence]
                    temp_len = len(sentence_words)

            if temp:
                chunks.append(". ".join(temp).strip())

        else:
            if current_length + para_len <= chunk_size:
                current_chunk.append(para)
                current_length += para_len
            else:
                chunks.append(" ".join(current_chunk).strip())
                current_chunk = [para]
                current_length = para_len

    if current_chunk:
        chunks.append(" ".join(current_chunk).strip())

    return chunks