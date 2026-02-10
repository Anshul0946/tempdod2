# Quick Start Guide - 5G DOD Processor

## ⚡ Fast Track

1.  **Run the App**:
    ```bash
    streamlit run app.py
    ```

2.  **Authenticate**:
    -   Enter your **NVIDIA API Key** in the sidebar.
    -   The app uses **PaddleOCR** (text extraction) and **DeepSeek** (reasoning).

3.  **Process**:
    -   Upload your `.xlsx` template.
    -   Click **Process**.
    -   Watch the live logs as the pipeline extracts and validates data.

## 🛠️ What's New?

-   **Faster**: Vision model removed in favor of PaddleOCR.
-   **Smarter**: Validation Agent fixes OCR typos (e.g., `O` vs `0`).
-   **Stricter**: Images are strictly classified by column/row. No mixing.

## 📂 Troubleshooting

-   **"No images found"**: Ensure your Excel file has actual embedded images, not floating shapes.
-   **"Validation failed"**: The agent couldn't find required parameters. Check image clarity.
-   **"API Error"**: Verify your NVIDIA API key has credits.
