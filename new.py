def answer_with_rag(question: str):
    # 1. 从企业知识库检索相关资料
    docs = vector_db.search(question, top_k=5)

    # 2. 组织检索到的上下文
    context = "\n\n".join([doc.content for doc in docs])

    # 3. 构造提示词，要求 AI 只能基于资料回答
    prompt = f"""
    请基于以下企业资料回答问题。
    如果资料中没有依据，请说明无法判断。

    企业资料：
    {context}

    用户问题：
    {question}
    """

    # 4. 调用大模型生成回答
    answer = llm.generate(prompt)

    # 5. 返回答案和引用来源
    sources = [doc.source for doc in docs]
    return answer, sources