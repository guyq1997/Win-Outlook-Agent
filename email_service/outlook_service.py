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
                best_match = None
                best_score = 0
                best_name = None
                MIN_MATCH_SCORE = 1

                def get_match_score(contact_name, search_term):
                    search_term = search_term.lower()
                    contact_name = contact_name.lower()
                    
                    # Split names into parts
                    search_parts = search_term.split()
                    contact_parts = contact_name.split()
                    
                    # Exact match
                    if contact_name == search_term:
                        return 4
                    
                    # Check if all search parts are in contact name
                    if all(part in contact_name for part in search_parts):
                        return 3
                    
                    # Check for first name or last name exact matches
                    if any(search_part == contact_part 
                          for search_part in search_parts 
                          for contact_part in contact_parts):
                        return 2
                    
                    # Partial matches in any part
                    if any(search_part in contact_part 
                          for search_part in search_parts 
                          for contact_part in contact_parts):
                        return 1
                    
                    return 0

                # 1. Search recent emails (more reliable than AutoComplete)
                logger.debug("Searching recent emails...")
                recent_contacts = {}
                try:
                    sent_items = self.namespace.GetDefaultFolder(5)  # Sent Items folder
                    for item in sent_items.Items.Restrict("[SentOn] > '" + 
                            (datetime.now() - timedelta(days=30)).strftime('%m/%d/%Y %H:%M %p') + "'"):
                        if item.To:
                            for recipient in item.To.split(';'):
                                recipient = recipient.strip()
                                if recipient and '@' in recipient:
                                    recent_contacts[recipient] = recipient
                except Exception as e:
                    logger.warning(f"Failed to search recent emails: {str(e)}")

                # 2. Search contacts folder
                logger.debug("Searching contacts folder...")
                contacts = {}
                try:
                    contacts_folder = self.namespace.GetDefaultFolder(10)
                    for contact in contacts_folder.Items:
                        if contact.Class == 40:  # OlObjectClass.olContact
                            name = f"{contact.FirstName} {contact.LastName}".strip()
                            if contact.Email1Address:
                                contacts[name] = contact.Email1Address
                except Exception as e:
                    logger.warning(f"Failed to search contacts folder: {str(e)}")

                # 3. Search Global Address List
                logger.debug("Searching Global Address List...")
                try:
                    for list_name in self.namespace.AddressLists:
                        if "Global Address List" in list_name.Name:
                            gal = list_name
                            for entry in gal.AddressEntries:
                                try:
                                    if entry.AddressEntryUserType == 0:
                                        user = entry.GetExchangeUser()
                                        if user:
                                            name = user.Name
                                            email = user.PrimarySmtpAddress
                                            for possible in possible_names:
                                                score = get_match_score(name, possible)
                                                if score > best_score:
                                                    best_score = score
                                                    best_name = possible
                                                    best_match = email
                                except Exception as entry_error:
                                    logger.debug(f"Skipping GAL entry due to error: {str(entry_error)}")
                            break
                except Exception as e:
                    logger.warning(f"Failed to search GAL: {str(e)}")

                # Combine and evaluate all results
                combined = {**recent_contacts, **contacts}
                for name, email in combined.items():
                    for possible in possible_names:
                        score = get_match_score(name, possible)
                        if score > best_score:
                            best_score = score
                            best_name = possible
                            best_match = email

                # Return tuple as specified in the docstring
                return f"The most likely email address of the recipient {possible_names} is: {best_match}" if best_match and best_score >= MIN_MATCH_SCORE else None


            except Exception as e:
                logger.error(f"Failed to find email: {str(e)}", exc_info=True)
                raise ValueError(f"Email lookup failed: {str(e)}")

     