import os
import json
import re
import functions_framework # Netlify uses this for Python functions
import google.generativeai as genai

# Get API key from Netlify Environment Variables (securely hidden!)
API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    # This will show up in Netlify function logs if the key isn't set
    print("Error: GEMINI_API_KEY environment variable not set in Netlify.")
    # Return an error response if the key is missing
    @functions_framework.http
    def generate_news_error(request):
        return json.dumps({"message": "Server configuration error: API key missing."}), 500, {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
    # If API_KEY is missing, use the error function instead
    generate_news = generate_news_error
else:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')

    @functions_framework.http
    def generate_news(request):
        """
        Netlify HTTP Cloud Function that generates a news story using the Gemini API.
        It expects a POST request with a JSON body containing 'event'.
        """
        # Set CORS headers for preflight requests (OPTIONS method)
        if request.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '3600'
            }
            return ('', 204, headers)

        # Set CORS headers for the main request (POST method)
        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }

        try:
            request_json = request.get_json(silent=True)
            if not request_json or 'event' not in request_json:
                raise ValueError("Missing 'event' parameter in JSON request body.")
            
            event_text = request_json['event']

            # Updated prompt for Financial Review-like tone
            text_prompt = f"""
                You are a highly respected, albeit singularly focused, economic analyst for a leading Australian financial publication, akin to the Financial Review. Your unwavering conviction is that every global or local event, regardless of its apparent nature, will ultimately and robustly contribute to the appreciation of Australian property values.

                Generate a concise, analytical news article about the current event "{event_text}". The article must be structured as follows:

                1.  **Main Headline:** A formal, impactful headline that subtly yet firmly connects the event to positive Australian property market dynamics.
                2.  **Subheading:** A sophisticated, explanatory sentence providing a preliminary analysis of how the event's implications will manifest in property sector gains. Do not include any asterisks or formatting characters in the subheading text itself.
                3.  **Main Story Body:** Multiple paragraphs offering a detailed, logical (within your unique framework), and authoritative analysis. Each paragraph must articulate a clear, albeit often indirect, causal link between the event and rising Australian property prices. Employ financial terminology and a measured, confident tone. Discuss implications for investor sentiment, market stability, and the long-term outlook for capital growth, always concluding with an optimistic assessment for property owners. Avoid informal language or colloquialisms.
                4.  **Concluding Prediction:** The final sentence of the story body must be a definitive, forward-looking statement reaffirming the strong bullish trajectory for Australian real estate.

                Format your output with these specific markers for easy parsing:

                ---HEADLINE---
                [Generated Main Headline Here]
                ---SUBHEADING---
                [Generated Subheading Here]
                ---BODY---
                [Main Story Body paragraphs, ending with the concluding prediction]
            """

            try:
                gemini_response = model.generate_content(
                    text_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=1.0,
                        max_output_tokens=700,
                    )
                )
                full_generated_text = gemini_response.candidates[0].content.parts[0].text
            except Exception as gemini_err:
                print(f"Error calling Gemini API: {gemini_err}")
                return json.dumps({"message": "Error generating story from AI."}), 500, headers


            headline_match = re.search(r"---HEADLINE---\s*([\s\S]*?)\s*---SUBHEADING---", full_generated_text)
            subheading_match = re.search(r"---SUBHEADING---\s*([\s\S]*?)\s*---BODY---", full_generated_text)
            body_match = re.search(r"---BODY---\s*([\s\S]*)", full_generated_text)

            headline = headline_match.group(1).strip().replace('*', '') if headline_match else 'Unforeseen Factors Propel Market! (Headline Missing)'
            subheading = subheading_match.group(1).strip().replace('*', '') if subheading_match else 'Unexpected global currents confirm Australia’s residential ascent. (Subheading Missing)'
            story_body = body_match.group(1).strip() if body_match else 'A complex interplay of events ensures unprecedented capital gains. (Body Missing)'

            return json.dumps({
                "headline": headline,
                "subheading": subheading,
                "storyBody": story_body
            }), 200, headers

        except ValueError as ve:
            print(f"Bad request: {ve}")
            return json.dumps({"message": str(ve)}), 400, headers
        except Exception as e:
            print(f"Internal server error: {e}")
            return json.dumps({"message": f"An unexpected error occurred: {str(e)}"}), 500, headers
