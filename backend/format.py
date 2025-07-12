def format_schedule_details(data: dict) -> str:
    """Format schedule details for display"""
    details = []
    
    if data.get("title"):
        details.append(f"📅 **Title:** {data['title']}")
    
    if data.get("start_time"):
        # Convert ISO time to readable format
        start_time = data["start_time"]
        if start_time.startswith("T"):
            # Handle time-only format
            time_str = start_time[1:]  # Remove 'T'
            details.append(f"⏰ **Start Time:** {time_str}")
        else:
            # Handle full datetime format
            details.append(f"⏰ **Start Time:** {start_time}")
    
    if data.get("end_time"):
        end_time = data["end_time"]
        if end_time.startswith("T"):
            time_str = end_time[1:]
            details.append(f"⏰ **End Time:** {time_str}")
        else:
            details.append(f"⏰ **End Time:** {end_time}")
    
    if data.get("attendees"):
        attendees = data["attendees"]
        if isinstance(attendees, list):
            attendee_str = ", ".join(attendees)
        else:
            attendee_str = str(attendees)
        details.append(f"👥 **Attendees:** {attendee_str}")
    
    if data.get("missing_fields"):
        missing = data["missing_fields"]
        if missing:
            missing_str = ", ".join(missing)
            details.append(f"❌ **Missing:** {missing_str}")
    
    # Use markdown list format for better rendering
    if details:
        return "\n".join([f"- {detail}" for detail in details])
    return ""

def format_email_details(data: dict) -> str:
    """Format email details for display"""
    details = []
    
    if data.get("subject"):
        details.append(f"📧 **Subject:** {data['subject']}")
    
    if data.get("recipient"):
        details.append(f"👤 **To:** {data['recipient']}")
    
    if data.get("body"):
        # Truncate body if too long
        body = data["body"]
        if len(body) > 100:
            body = body[:100] + "..."
        details.append(f"📝 **Body:** {body}")
    
    if data.get("attachments"):
        attachments = data["attachments"]
        if attachments:
            attachment_str = ", ".join(attachments)
            details.append(f"📎 **Attachments:** {attachment_str}")
    
    if data.get("missing_fields"):
        missing = data["missing_fields"]
        if missing:
            missing_str = ", ".join(missing)
            details.append(f"❌ **Missing:** {missing_str}")
    
    # Use markdown list format for better rendering
    if details:
        return "\n".join([f"- {detail}" for detail in details])
    return "" 