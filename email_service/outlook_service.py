"""
Outlook service module for handling email draft creation and management through COM automation.
"""

import win32com.client
import pythoncom
from typing import Dict, Optional
import asyncio
from loguru import logger
import os
import time
import threading
import subprocess
from datetime import datetime, timedelta

class OutlookService:
    def __init__(self):
        """Initialize the Outlook service with COM automation."""
        self.outlook = None
        self.namespace = None  # Add namespace as class property
        self._thread_id = None
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize Outlook connection, starting Outlook if needed"""
        try:
            # Check if already initialized
            if self.outlook is not None and self.namespace is not None:
                logger.debug("Outlook already initialized")
                return

            # Try to get Outlook instance
            try:
                self.outlook = win32com.client.Dispatch("Outlook.Application")
                self.namespace = self.outlook.GetNamespace("MAPI")  # Store namespace reference
            except Exception as e:
                logger.info("Outlook not running, attempting to start...")
                
                # Start Outlook
                subprocess.Popen(["outlook.exe"])
                
                # Wait for Outlook to start (up to 30 seconds)
                for _ in range(30):
                    try:
                        self.outlook = win32com.client.Dispatch("Outlook.Application")
                        self.namespace = self.outlook.GetNamespace("MAPI")  # Store namespace reference
                        break
                    except Exception:
                        await asyncio.sleep(1)
                else:
                    raise TimeoutError("Timeout waiting for Outlook to start")

            logger.info("Outlook service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Outlook service: {str(e)}")
            raise RuntimeError(f"Outlook initialization failed: {str(e)}")
            
    async def create_draft(self, to: str = None, subject: str = None, body: str = None, 
                         priority: str = "normal", attachments: list = None) -> str:
        """
        Create a draft email and return its Entry ID.
        

        Args:
            to (str): Recipient email address
            subject (str): Email subject
            body (str): Email body content
            priority (str): Email priority (normal or high)
            attachments (list): List of attachment paths

            
        Returns:
            str: The Entry ID of the created draft
            
        Raises:
            ValueError: If email creation fails or required fields are missing
        """
        async with self._lock:
            try:
                logger.debug("Initializing Outlook for draft creation...")
                await self.initialize()
                
                logger.debug("Creating new mail item...")
                mail_item = self.outlook.CreateItem(0)  # olMailItem
                
                # Set basic properties with debug logging
                if to:
                    logger.debug(f"Setting recipient(s): {to}")
                    mail_item.To = to
                if subject:
                    logger.debug(f"Setting subject: {subject}")
                    mail_item.Subject = subject
                if body:
                    logger.debug("Setting email body")
                    mail_item.Body = body
                
                if priority == "high":
                    logger.debug("Setting high priority")
                    mail_item.Importance = 2
                
                if attachments:
                    for attachment in attachments:
                        if os.path.exists(attachment):
                            logger.debug(f"Adding attachment: {attachment}")
                            mail_item.Attachments.Add(attachment)
                        else:
                            logger.warning(f"Attachment not found: {attachment}")
                
                logger.debug("Saving draft...")
                mail_item.Save()
                entry_id = mail_item.EntryID
                logger.debug(f"Draft saved with Entry ID: {entry_id}")
                
                # Single window display operation
                logger.debug("Displaying mail item")
                mail_item.Display(True)  # True parameter forces the window to the front
                
                return entry_id

            except Exception as e:
                logger.error(f"Failed to create email draft: {str(e)}", exc_info=True)
                raise ValueError(f"Draft creation failed: {str(e)}")
            
            
    async def cleanup(self):
        """Release COM resources and uninitialize COM for the current thread."""
        if self._thread_id == threading.get_ident():
            try:
                # Release COM objects
                if self.namespace:
                    self.namespace = None
                if self.outlook:
                    self.outlook = None
                    
                # Uninitialize COM
                pythoncom.CoUninitialize()
                self._thread_id = None
                
                logger.info("Outlook COM resources cleaned up successfully")
                
            except Exception as e:
                logger.error(f"Error during COM cleanup: {str(e)}")
                raise

    async def find_most_likely_email(self, possible_names: list[str]) -> tuple[str, str]:
        """
        Find the most likely email address of one recipient from a list of possible names by searching
        the Global Address List.
        
        Args:
            possible_names: List of possible contact names to search for
            
        Returns:
            tuple: (matched_name, email_address) The best matching name and its email
                  Returns (None, None) if no match is found
            
        Raises:
            ValueError: If Outlook access fails
        """
        async with self._lock:
            try:
                await self.initialize()
                
                # Create a temporary mail item to use recipient resolution
                mail_item = self.outlook.CreateItem(0)  # olMailItem
                
                best_match = None
                best_match_score = 0
                
                for name in possible_names:
                    try:
                        # Add recipient to resolve
                        recipient = mail_item.Recipients.Add(name)
                        
                        # Resolve the name against the address book
                        if recipient.Resolve():
                            # Calculate match score (exact match gets highest score)
                            match_score = 0
                            resolved_name = recipient.Name.lower()
                            search_name = name.lower()
                            
                            if resolved_name == search_name:
                                match_score = 100
                            elif search_name in resolved_name:
                                match_score = 75
                            elif any(part in resolved_name for part in search_name.split()):
                                match_score = 50
                                
                            # Update best match if this score is higher
                            if match_score > best_match_score:
                                email_address = recipient.AddressEntry.GetExchangeUser().PrimarySmtpAddress
                                best_match = (recipient.Name, email_address)
                                best_match_score = match_score
                                
                    except Exception as e:
                        logger.debug(f"Failed to resolve '{name}': {str(e)}")
                        continue
                
                # Clean up
                mail_item = None
                
                return "The email address of the recipient is: " + best_match[1] if best_match else "None"

            except Exception as e:
                logger.error(f"Failed to find email: {str(e)}", exc_info=True)
                raise ValueError(f"Email lookup failed: {str(e)}")

     