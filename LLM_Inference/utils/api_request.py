from openai import AzureOpenAI, BadRequestError, RateLimitError, APIConnectionError
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def create_gpt4_config(message, 
                       model = "gpt-4.1-mini",
                       stop = "# Provide a fix for the buggy function",
                       max_tokens=3000,
                       top_p = 1,
                       temperature = 0,
                       system_message = None):
    # New OpenAI SDK format
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": message})
    
    return {
        "messages": messages,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "temperature": temperature,
        "stop": stop
    }

def create_openai_config(message,
                         model="gpt-3.5-turbo",
                         stop="# Provide a fix for the buggy function",
                         max_tokens=3000,
                         top_p=1,
                         temperature=0,
                         system_message=None):
    # New OpenAI SDK format
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": message})
    
    return {
        "messages": messages,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "temperature": temperature,
        "stop": stop
    }


def create_openai_config_suffix(prompt, suffix,
                                engine_name="code-davinci-002",
                                max_tokens=500,
                                top_p=1,
                                temperature=0):
    # Note: This function is for legacy completion API (deprecated)
    # New chat completions API doesn't support suffix parameter
    return {
        "prompt": prompt,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "temperature": temperature,
        "suffix": suffix
    }


def create_openai_config_single(prompt, stop,
                                engine_name="code-davinci-002",
                                max_tokens=100,
                                top_p=1,
                                temperature=0):
    # Note: This function is for legacy completion API (deprecated)
    return {
        "prompt": prompt,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "temperature": temperature,
        "logprobs": 1,
        "stop": stop
    }


# Handles requests to Azure OpenAI API
def request_engine(config):
    ret = None
    # Get deployment name from environment
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    
    while ret is None:
        try:
            # Call Azure OpenAI API with deployment name
            response = client.chat.completions.create(
                model=deployment,
                messages=config['messages'],
                max_tokens=config.get('max_tokens', 3000),
                temperature=config.get('temperature', 0.0),
                top_p=config.get('top_p', 0.95),
                stop=config.get('stop', None)
            )
            
            # Convert response to dict format for compatibility
            ret = {
                "choices": [
                    {
                        "message": {
                            "content": response.choices[0].message.content
                        },
                        "finish_reason": response.choices[0].finish_reason
                    }
                ]
            }
        except BadRequestError as e:
            print(e)
            if "Please reduce your prompt" in str(e) or "maximum context length" in str(e):
                config['max_tokens'] = config['max_tokens'] - 200
                if config['max_tokens'] < 100:
                    return None
            else:
                return None
        except RateLimitError as e:
            print(f"Rate limit exceeded: {e}. Waiting...")
            time.sleep(60)
        except APIConnectionError as e:
            print(f"API connection error: {e}. Waiting...")
            time.sleep(5)
        except Exception as e:
            print(f"Unknown error: {e}. Waiting...")
            time.sleep(5)
    return ret
