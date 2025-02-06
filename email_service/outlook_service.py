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
        Find the most likely email address from a list of possible contact names.
        
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
                best_match = None
                best_score = -1
                best_name = None
                
                contacts_folder = self.namespace.GetDefaultFolder(10)  # 10 = olFolderContacts
                
                # Build filter for all possible names
                filter_conditions = []
                for name in possible_names:
                    filter_conditions.append(f"[FileAs] LIKE '%{name}%' OR [FullName] LIKE '%{name}%'")
                filter_string = " OR ".join(filter_conditions)
                
                matches = contacts_folder.Items.Restrict(filter_string)
                
                # Look through all matching contacts
                for contact in matches:
                    if not hasattr(contact, 'Email1Address') or not contact.Email1Address:
                        continue
                        
                    # Calculate match score for this contact
                    try:
                        # Base score from usage frequency
                        score = getattr(contact, 'ContactCount', 0)
                        
                        # Add recency bonus
                        if hasattr(contact, 'LastModificationTime') and contact.LastModificationTime:
                            days_since_used = (time.time() - time.mktime(contact.LastModificationTime.timetuple())) / (24 * 3600)
                            if days_since_used < 30:  # Used in last month
                                score += 10
                            if days_since_used < 7:   # Used in last week
                                score += 20
                        
                        # Add exact name match bonus
                        contact_name = contact.FullName or contact.FileAs or ""
                        for name in possible_names:
                            if name.lower() == contact_name.lower():
                                score += 50  # Big bonus for exact match
                            elif name.lower() in contact_name.lower():
                                score += 25  # Smaller bonus for partial match
                        
                        if score > best_score:
                            best_score = score
                            best_match = contact.Email1Address
                            best_name = contact_name
                            
                    except Exception as e:
                        logger.debug(f"Error scoring contact {contact.FullName}: {str(e)}")
                        # If we can't calculate score but haven't found any match yet
                        if best_match is None:
                            best_match = contact.Email1Address
                            best_name = contact.FullName
                
                if best_match:
                    logger.info(f"Found best matching email for names {possible_names}: {best_name} <{best_match}>")
                else:
                    logger.info(f"No matching email found for names {possible_names}")
                
                return (best_name, best_match) if best_match else (None, None)
                
            except Exception as e:
                logger.error(f"Failed to find email address: {str(e)}")
                raise ValueError(f"Email lookup failed: {str(e)}")