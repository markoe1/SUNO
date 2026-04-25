"""Campaign and clip processing pipeline"""

from suno.campaigns.ingestion import CampaignIngestionManager, CampaignMetadataNormalizer
from suno.campaigns.eligibility import ClipEligibilityChecker, AssignmentQueueManager
from suno.campaigns.caption_generator import CaptionGenerator, SchedulingManager
from suno.campaigns.job_executor import CaptionJobExecutor, PostingJobExecutor, JobMonitor

__all__ = [
    "CampaignIngestionManager",
    "CampaignMetadataNormalizer",
    "ClipEligibilityChecker",
    "AssignmentQueueManager",
    "CaptionGenerator",
    "SchedulingManager",
    "CaptionJobExecutor",
    "PostingJobExecutor",
    "JobMonitor",
]
