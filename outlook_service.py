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
            
    async def create_draft(self, email_data: Dict) -> str:
        """
        Create a draft email and return its Entry ID.
        
        Args:
            email_data: Dictionary containing email fields (to, subject, body, priority, attachments)
            
        Returns:
            str: The Entry ID of the created draft
            
        Raises:
            ValueError: If email creation fails or required fields are missing
        """
        async with self._lock:
            try:
                await self.initialize()
                
                # Create new mail item
                mail_item = self.outlook.CreateItem(0)  # olMailItem
                
                # Set basic properties using the email_data dict
                mail_item.To = email_data["to"]
                mail_item.Subject = email_data["subject"]
                mail_item.Body = email_data["body"]
                
                # Set priority if specified
                if email_data.get("priority") == "high":
                    mail_item.Importance = 2  # High importance
                
                # Add attachments if any
                for attachment in email_data.get("attachments", []):
                    if os.path.exists(attachment):
                        mail_item.Attachments.Add(attachment)
                    else:
                        logger.warning(f"Attachment not found: {attachment}")
                
                # Save as draft
                mail_item.Save()
                entry_id = mail_item.EntryID
                
                logger.info(f"Created draft email with ID: {entry_id}")
                return entry_id
                
            except Exception as e:
                logger.error(f"Failed to create email draft: {str(e)}")
                raise ValueError(f"Draft creation failed: {str(e)}")
            
    async def display_draft(self, entry_id: str):
        """
        Display a draft email for user review.
        
        Args:
            entry_id: The Entry ID of the draft to display
            
        Raises:
            ValueError: If the draft cannot be found or displayed
        """
        async with self._lock:
            try:
                await self.initialize()
                
                # Get the mail item by Entry ID
                mail_item = self.namespace.GetItemFromID(entry_id)
                
                # Display and activate the item window
                inspector = mail_item.GetInspector()
                mail_item.Display()
                
                # Modified window activation sequence
                try:
                    inspector.WindowState = 2  # Maximize window first
                    await asyncio.sleep(0.5)  # Add short delay for window initialization
                    inspector.Activate()  # Now bring to foreground
                except Exception as e:
                    logger.warning(f"Window activation failed: {str(e)} (proceeding anyway)")
                
                logger.info(f"Displayed draft email with ID: {entry_id}")
                
            except Exception as e:
                logger.error(f"Failed to display draft: {str(e)}")
                raise ValueError(f"Cannot display draft: {str(e)}")
            
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