SUMMARISE = f"""Create a {request.summary_length} summary of these {len(docs)} documents.
        Focus on key themes, patterns, and notable exceptions. 
        Length guide:
        - Short: 1-2 paragraphs
        - Medium: 3-5 paragraphs
        - Detailed: Comprehensive analysis

        Documents:
        {formatted_docs[:15000]}
        """