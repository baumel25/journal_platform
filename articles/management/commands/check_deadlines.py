from django.core.management.base import BaseCommand
from django.utils import timezone
from articles.models import ReviewInvitation, Review
from articles.utils import send_deadline_reminder


class Command(BaseCommand):
    help = 'Check all active review deadlines and send milestone reminders'

    def handle(self, *args, **options):
        now = timezone.now()
        milestones = [50, 75, 80, 85, 90, 95, 98]
        notified_count = 0
        skipped_count = 0

        # Get all accepted invitations with a deadline set
        invitations = ReviewInvitation.objects.filter(
            status='accepted',
            deadline__isnull=False,
        ).select_related('article', 'reviewer')

        self.stdout.write(f"Checking {invitations.count()} active review deadlines...")

        for invitation in invitations:
            # Skip if the review has already been submitted
            review = Review.objects.filter(
                article=invitation.article,
                reviewer=invitation.reviewer,
            ).exclude(comments_to_author='').exclude(comments_to_author__isnull=True).first()

            if review:
                skipped_count += 1
                continue

            # Calculate elapsed percentage
            total_duration = invitation.deadline - invitation.responded_at
            elapsed = now - invitation.responded_at

            if total_duration.total_seconds() <= 0:
                # Deadline already passed — skip milestone tracking
                skipped_count += 1
                continue

            pct = (elapsed.total_seconds() / total_duration.total_seconds()) * 100

            # Check each milestone
            for milestone in milestones:
                milestone_key = str(milestone)
                if pct >= milestone and milestone_key not in invitation.milestones_notified:
                    # Send the reminder
                    try:
                        send_deadline_reminder(invitation, milestone)
                        invitation.milestones_notified[milestone_key] = now.isoformat()
                        invitation.save(update_fields=['milestones_notified'])
                        notified_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ Sent {milestone}% reminder to {invitation.reviewer.email} "
                                f"for '{invitation.article.title}'"
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ Failed to send {milestone}% reminder to "
                                f"{invitation.reviewer.email}: {e}"
                            )
                        )

        self.stdout.write(self.style.SUCCESS(
            f"\nDone! Sent {notified_count} reminder(s). "
            f"Skipped {skipped_count} completed/expired review(s)."
        ))
