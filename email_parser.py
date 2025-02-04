"""
Email parser module for converting voice commands into structured email components using GPT-4o.
Handles natural language processing and function calling to extract email fields.
"""

import json
from typing import Dict, Optional
import asyncio
from loguru import logger

from llm_api import query_llm

class EmailParser:
    def __init__(self, model: str = "gpt-4o"):
        """Initialize the email parser with specified LLM model."""
        self.model = model
        self._system_prompt = """
        You are an email drafting assistant. Convert voice commands into structured email components.
        Focus on extracting: recipient, subject, body, and any special instructions (priority, attachments).
        Keep responses concise and business-appropriate.
        
        Examples:
        1. "Send an email to John about tomorrow's meeting" ->
           {"to": "John", "subject": "Tomorrow's Meeting", "body": "I wanted to discuss tomorrow's meeting.", "priority": "normal"}
        2. "Urgent message to Sarah about the project delay" ->
           {"to": "Sarah", "subject": "Urgent: Project Delay Update", "body": "I need to inform you about a delay in the project.", "priority": "high"}
        """

    async def parse_email(self, text: str) -> Dict:
        """
        Parse a voice command into structured email components.
        
        Args:
            text: The voice command text to parse
            
        Returns:
            Dict containing email components (to, subject, body, priority, attachments)
            
        Raises:
            ValueError: If parsing fails or required fields are missing
        """
        try:
            logger.info(f"Parsing voice command: {text}")
            
            # Call LLM with function calling
            response = await self._call_llm(text)
            
            # Validate and process response
            email_data = self._validate_response(response)
            
            logger.info(f"Successfully parsed email data: {json.dumps(email_data, indent=2)}")
            return email_data
            
        except Exception as e:
            logger.error(f"Failed to parse email command: {str(e)}")
            raise ValueError(f"Email parsing failed: {str(e)}")

    async def _call_llm(self, text: str) -> Dict:
        """Call LLM with function calling for email parsing."""
        try:
            # Prepare the prompt with the voice command
            prompt = f"Parse this voice command into email components: {text}"
            
            # Call LLM with function schema
            response = query_llm(
                prompt=self._system_prompt + "\n\n" + prompt,
                provider="openai",
                model=self.model,
            )
            
            # Add debug logging for raw response
            logger.debug(f"Raw LLM response: {response}")
            
            try:
                parsed_response = json.loads(response)
                logger.debug(f"Successfully parsed JSON: {json.dumps(parsed_response, indent=2)}")
                return parsed_response
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed. Response content: {response}")
                logger.error(f"JSON error details: {str(e)}")
                raise ValueError(f"Invalid JSON response from LLM: {str(e)}")
                
        except Exception as e:
            logger.error(f"LLM call failed: {str(e)}")
            raise

    def _validate_response(self, data: Dict) -> Dict:
        """
        Validate and clean up the parsed email data.
        
        Args:
            data: Raw parsed email data from LLM
            
        Returns:
            Validated and cleaned email data dictionary
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            # Check required fields
            required_fields = ["to", "subject", "body"]
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
            # Clean and validate fields
            cleaned_data = {
                "to": data["to"].strip(),
                "subject": data["subject"].strip(),
                "body": data["body"].strip(),
                "priority": data.get("priority", "normal"),
                "attachments": data.get("attachments", [])
            }
            
            # Validate priority
            if cleaned_data["priority"] not in ["low", "normal", "high"]:
                cleaned_data["priority"] = "normal"
                
            # Validate attachments is a list
            if not isinstance(cleaned_data["attachments"], list):
                cleaned_data["attachments"] = []
                
            return cleaned_data
            
        except Exception as e:
            logger.error(f"Response validation failed: {str(e)}")
            raise ValueError(f"Invalid email data: {str(e)}") 