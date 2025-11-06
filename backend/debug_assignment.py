#!/usr/bin/env python3
"""Debug script to test ticket assignment"""

import sys
sys.path.insert(0, '/app')

from app.core.database import SessionLocal
from app.services.ticket_processor import TicketProcessor
from app.services.redmine_service import RedmineService
from datetime import datetime
import pytz

def main():
    db = SessionLocal()
    try:
        processor = TicketProcessor(db)
        redmine = RedmineService(db)

        print("Fetching new issues from Redmine...")
        issues = redmine.get_new_issues(limit=1)

        if not issues:
            print("No new issues found")
            return

        issue = issues[0]
        print(f"\nProcessing ticket #{issue['id']}: {issue['subject']}")

        # Extract ticket data
        ticket_data = processor._extract_ticket_data(issue)
        print(f"\nTicket data extracted:")
        print(f"  Priority: {ticket_data.get('adjusted_priority')}")
        print(f"  Environment: {ticket_data.get('environment')}")

        # Get AI analysis
        print(f"\nRunning AI analysis...")
        ai_analysis = processor.llm_service.analyze_ticket(ticket_data)
        category = ai_analysis['classification']['category']
        print(f"  Category: {category}")
        print(f"  Complexity: {ai_analysis['classification'].get('complexity')}")

        # Find best assignee
        print(f"\nFinding best assignee...")
        assignee, routing_info = processor._find_best_assignee(ticket_data, category)

        print(f"\nRESULT:")
        print(f"  Assignee: {assignee.name if assignee else 'NONE'}")
        print(f"  Routing Info: {routing_info}")

        if assignee:
            print(f"\n✅ SUCCESS - Would assign to {assignee.name}")
        else:
            print(f"\n❌ FAILURE - No assignee found")
            print(f"  Reason: {routing_info.get('error', 'Unknown')}")
            print(f"  Message: {routing_info.get('message', 'No message')}")

            # Debug: Check available members manually
            print(f"\n--- Debugging ---")
            team_level = "L2" if ticket_data['adjusted_priority'] == 'P1(Critical)' else "L1"
            print(f"  Team level: {team_level}")

            available = processor.workload_manager.get_available_members(team_level)
            print(f"  Available {team_level} members: {len(available)}")
            for m in available[:5]:
                print(f"    - {m.name} (ID: {m.id})")

            if available:
                print(f"\n  Testing smart_route_ticket directly...")
                best, conf, reasons = processor.ml_service.smart_route_ticket(
                    ticket_data, available, category
                )
                print(f"    Result: {best.name if best else 'NONE'}")
                print(f"    Confidence: {conf}")
                print(f"    Reasons: {reasons}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
