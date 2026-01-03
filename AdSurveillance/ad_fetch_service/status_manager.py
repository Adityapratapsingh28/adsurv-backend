"""
Status Manager - Tracks and manages ads fetching job status
"""
from datetime import datetime, timezone
import threading
import time
from typing import Dict, Any, Optional, List
from supabase import create_client, Client
import os
import sys

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

class StatusManager:
    """Manages status of ads fetching jobs"""
    
    def __init__(self):
        try:
            self.supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
            print("✅ StatusManager: Supabase connection established")
        except Exception as e:
            print(f"❌ StatusManager: Supabase connection failed: {e}")
            self.supabase = None
            
        self.active_jobs: Dict[str, Dict] = {}
        self.lock = threading.Lock()
    
    def update_job_status(self, job_id: str, status: str, **kwargs) -> bool:
        """
        Update job status in database
        
        Args:
            job_id: The job ID
            status: New status (pending, running, completed, failed)
            **kwargs: Additional fields to update
        
        Returns:
            True if successful, False otherwise
        """
        if not self.supabase:
            print(f"❌ StatusManager: Cannot update job {job_id} - Supabase not connected")
            return False
            
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Add any additional fields
            for key, value in kwargs.items():
                if value is not None:
                    update_data[key] = value
            
            # If job is completed or failed, set end_time
            if status in ['completed', 'failed'] and 'end_time' not in update_data:
                update_data['end_time'] = datetime.now(timezone.utc).isoformat()
            
            response = self.supabase.table('ads_fetch_jobs')\
                .update(update_data)\
                .eq('job_id', job_id)\
                .execute()
            
            # Update in-memory cache
            with self.lock:
                if job_id in self.active_jobs:
                    self.active_jobs[job_id].update(update_data)
                else:
                    # Get full job data if not in cache
                    full_job = self.get_job_status(job_id)
                    if full_job:
                        self.active_jobs[job_id] = full_job
            
            print(f"✅ StatusManager: Updated job {job_id} to status {status}")
            return True
        except Exception as e:
            print(f"❌ StatusManager: Error updating job {job_id} status: {e}")
            return False
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a job
        
        Args:
            job_id: The job ID
        
        Returns:
            Job status dictionary or None if not found
        """
        # Check in-memory cache first
        with self.lock:
            if job_id in self.active_jobs:
                return self.active_jobs[job_id].copy()
        
        # Fall back to database
        if not self.supabase:
            print(f"❌ StatusManager: Cannot get job {job_id} - Supabase not connected")
            return None
            
        try:
            response = self.supabase.table('ads_fetch_jobs')\
                .select('*')\
                .eq('job_id', job_id)\
                .execute()
            
            if response.data:
                job_data = response.data[0]
                
                # Calculate duration if not present
                if job_data.get('end_time') and job_data.get('start_time'):
                    start_dt = self.parse_timestamp(job_data['start_time'])
                    end_dt = self.parse_timestamp(job_data['end_time'])
                    
                    if start_dt and end_dt:
                        job_data['duration_seconds'] = int((end_dt - start_dt).total_seconds())
                
                # Update cache
                with self.lock:
                    self.active_jobs[job_id] = job_data
                
                return job_data
            return None
        except Exception as e:
            print(f"❌ StatusManager: Error getting job {job_id} status: {e}")
            return None
    
    def parse_timestamp(self, timestamp):
        """Parse timestamp string to datetime object with UTC timezone"""
        if not timestamp:
            return None
        
        if isinstance(timestamp, str):
            try:
                # Handle ISO format timestamps with or without timezone
                if timestamp.endswith('Z'):
                    timestamp = timestamp[:-1] + '+00:00'
                
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                # If datetime is naive (no timezone), make it UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                return dt
            except Exception as e:
                print(f"❌ Error parsing timestamp {timestamp}: {e}")
                return None
        elif isinstance(timestamp, datetime):
            # If it's already a datetime object, ensure it has timezone
            if timestamp.tzinfo is None:
                return timestamp.replace(tzinfo=timezone.utc)
            return timestamp
        return timestamp
    
    def register_job(self, job_id: str, user_id: str, platform: str = "all") -> bool:
        """
        Register a new job
        
        Args:
            job_id: The job ID
            user_id: User who initiated the job
            platform: Platform to fetch from
        
        Returns:
            True if successful, False otherwise
        """
        if not self.supabase:
            print(f"❌ StatusManager: Cannot register job - Supabase not connected")
            return False
            
        try:
            # Get competitor count for this user
            response = self.supabase.table('competitors')\
                .select('id', count='exact')\
                .eq('user_id', user_id)\
                .eq('is_active', True)\
                .execute()
            
            competitor_count = response.count or 0
            
            job_data = {
                'job_id': job_id,
                'user_id': user_id,
                'status': 'pending',
                'platform': platform,
                'total_competitors': competitor_count,
                'ads_fetched': 0,
                'start_time': datetime.now(timezone.utc).isoformat(),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            response = self.supabase.table('ads_fetch_jobs')\
                .insert(job_data)\
                .execute()
            
            # Add to cache
            with self.lock:
                self.active_jobs[job_id] = job_data
            
            print(f"✅ StatusManager: Registered new job {job_id} for user {user_id}")
            return True
        except Exception as e:
            print(f"❌ StatusManager: Error registering job {job_id}: {e}")
            return False
    
    def get_user_jobs(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get all jobs for a specific user
        
        Args:
            user_id: The user ID
            limit: Maximum number of jobs to return
        
        Returns:
            List of job dictionaries
        """
        if not self.supabase:
            print(f"❌ StatusManager: Cannot get user jobs - Supabase not connected")
            return []
            
        try:
            response = self.supabase.table('ads_fetch_jobs')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            jobs = response.data if response.data else []
            
            # Calculate durations for each job
            for job in jobs:
                if job.get('end_time') and job.get('start_time'):
                    start_dt = self.parse_timestamp(job['start_time'])
                    end_dt = self.parse_timestamp(job['end_time'])
                    
                    if start_dt and end_dt:
                        job['duration_seconds'] = int((end_dt - start_dt).total_seconds())
            
            return jobs
        except Exception as e:
            print(f"❌ StatusManager: Error getting jobs for user {user_id}: {e}")
            return []
    
    def cleanup_old_jobs(self, days_old: int = 7) -> int:
        """
        Clean up jobs older than specified days
        
        Args:
            days_old: Delete jobs older than this many days
        
        Returns:
            Number of jobs deleted
        """
        if not self.supabase:
            print(f"❌ StatusManager: Cannot cleanup jobs - Supabase not connected")
            return 0
            
        try:
            # Calculate cutoff date
            cutoff_date = (datetime.now(timezone.utc) - time.timedelta(days=days_old)).isoformat()
            
            # Delete old jobs
            response = self.supabase.table('ads_fetch_jobs')\
                .delete()\
                .lt('created_at', cutoff_date)\
                .execute()
            
            deleted_count = len(response.data) if response.data else 0
            
            # Clean up cache
            with self.lock:
                cutoff_timestamp = time.time() - (days_old * 24 * 3600)
                jobs_to_remove = []
                
                for job_id, job_data in self.active_jobs.items():
                    created_at = job_data.get('created_at')
                    if isinstance(created_at, str):
                        created_dt = self.parse_timestamp(created_at)
                        if created_dt:
                            created_ts = created_dt.timestamp()
                            if created_ts < cutoff_timestamp:
                                jobs_to_remove.append(job_id)
                
                for job_id in jobs_to_remove:
                    del self.active_jobs[job_id]
            
            print(f"✅ StatusManager: Cleaned up {deleted_count} old jobs")
            return deleted_count
        except Exception as e:
            print(f"❌ StatusManager: Error cleaning up old jobs: {e}")
            return 0
    
    def get_job_statistics(self, user_id: str = None) -> Dict[str, Any]:
        """
        Get statistics about jobs
        
        Args:
            user_id: Optional user ID to filter by
        
        Returns:
            Dictionary with statistics
        """
        if not self.supabase:
            print(f"❌ StatusManager: Cannot get statistics - Supabase not connected")
            return {}
            
        try:
            query = self.supabase.table('ads_fetch_jobs').select('*')
            
            if user_id:
                query = query.eq('user_id', user_id)
            
            response = query.execute()
            jobs = response.data if response.data else []
            
            stats = {
                'total_jobs': len(jobs),
                'completed': 0,
                'failed': 0,
                'running': 0,
                'pending': 0,
                'total_ads_fetched': 0,
                'total_duration_seconds': 0,
                'avg_duration_seconds': 0
            }
            
            total_duration = 0
            completed_with_duration = 0
            
            for job in jobs:
                status = job.get('status', 'unknown')
                if status in stats:
                    stats[status] += 1
                
                ads_fetched = job.get('ads_fetched', 0)
                stats['total_ads_fetched'] += ads_fetched
                
                if job.get('duration_seconds'):
                    total_duration += job['duration_seconds']
                    completed_with_duration += 1
            
            if completed_with_duration > 0:
                stats['total_duration_seconds'] = total_duration
                stats['avg_duration_seconds'] = total_duration / completed_with_duration
            
            return stats
        except Exception as e:
            print(f"❌ StatusManager: Error getting job statistics: {e}")
            return {}
    
    def is_job_running(self, user_id: str = None, job_id: str = None) -> bool:
        """
        Check if a job is currently running
        
        Args:
            user_id: Optional user ID to check for running jobs
            job_id: Optional specific job ID to check
        
        Returns:
            True if a job is running, False otherwise
        """
        if not self.supabase:
            print(f"❌ StatusManager: Cannot check running jobs - Supabase not connected")
            return False
            
        try:
            query = self.supabase.table('ads_fetch_jobs')\
                .select('id')\
                .eq('status', 'running')
            
            if user_id:
                query = query.eq('user_id', user_id)
            
            if job_id:
                query = query.eq('job_id', job_id)
            
            response = query.limit(1).execute()
            
            return len(response.data) > 0 if response.data else False
        except Exception as e:
            print(f"❌ StatusManager: Error checking if job is running: {e}")
            return False
    
    def format_job_for_display(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a job for display in frontend
        
        Args:
            job: The job dictionary
        
        Returns:
            Formatted job dictionary
        """
        formatted = job.copy()
        
        # Add status icon
        status = job.get('status', 'unknown')
        status_icons = {
            'completed': '✅',
            'running': '🔄',
            'failed': '❌',
            'pending': '⏳'
        }
        formatted['status_icon'] = status_icons.get(status, '❓')
        
        # Format duration
        duration = job.get('duration_seconds')
        if not duration and job.get('end_time') and job.get('start_time'):
            start_dt = self.parse_timestamp(job['start_time'])
            end_dt = self.parse_timestamp(job['end_time'])
            if start_dt and end_dt:
                duration = int((end_dt - start_dt).total_seconds())
                formatted['duration_seconds'] = duration
        
        if duration:
            if duration < 60:
                formatted['duration_formatted'] = f"{duration}s"
            elif duration < 3600:
                minutes = duration // 60
                seconds = duration % 60
                formatted['duration_formatted'] = f"{minutes}m {seconds}s"
            else:
                hours = duration // 3600
                minutes = (duration % 3600) // 60
                formatted['duration_formatted'] = f"{hours}h {minutes}m"
        else:
            formatted['duration_formatted'] = 'N/A'
        
        # Calculate progress percentage
        if status == 'completed':
            formatted['progress'] = 100
        elif status == 'failed':
            formatted['progress'] = 0
        elif status == 'running':
            # Estimate progress based on time elapsed
            start_time = job.get('start_time')
            if start_time:
                start_dt = self.parse_timestamp(start_time)
                if start_dt:
                    now = datetime.now(timezone.utc)
                    elapsed = (now - start_dt).total_seconds()
                    
                    # Estimate total time: 30 seconds per platform per competitor
                    total_competitors = job.get('total_competitors', 1)
                    platform = job.get('platform', 'all')
                    
                    if platform == 'all':
                        platforms_count = 4
                    else:
                        platforms_count = 1
                    
                    estimated_total = total_competitors * 30 * platforms_count
                    estimated_total = min(estimated_total, 300)  # Cap at 5 minutes
                    
                    if estimated_total > 0:
                        progress = min(95, (elapsed / estimated_total) * 100)
                        formatted['progress'] = round(progress, 1)
                    else:
                        formatted['progress'] = 50
                else:
                    formatted['progress'] = 0
            else:
                formatted['progress'] = 0
        else:
            formatted['progress'] = 0
        
        # Format timestamps
        for time_field in ['start_time', 'end_time', 'created_at', 'updated_at']:
            if job.get(time_field):
                dt = self.parse_timestamp(job[time_field])
                if dt:
                    formatted[f'{time_field}_formatted'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        
        return formatted
    
    def mark_job_as_stuck(self, job_id: str) -> bool:
        """
        Mark a job as stuck (running for too long)
        
        Args:
            job_id: The job ID
        
        Returns:
            True if successful, False otherwise
        """
        return self.update_job_status(
            job_id,
            'failed',
            error_message='Job was stuck and automatically failed',
            end_time=datetime.now(timezone.utc).isoformat()
        )
    
    def get_stuck_jobs(self, max_minutes: int = 30) -> List[str]:
        """
        Get jobs that have been running for too long
        
        Args:
            max_minutes: Maximum minutes a job should run
        
        Returns:
            List of stuck job IDs
        """
        if not self.supabase:
            return []
            
        try:
            # Calculate cutoff time
            cutoff_time = (datetime.now(timezone.utc) - time.timedelta(minutes=max_minutes)).isoformat()
            
            # Find stuck jobs
            response = self.supabase.table('ads_fetch_jobs')\
                .select('job_id, start_time')\
                .eq('status', 'running')\
                .lt('start_time', cutoff_time)\
                .execute()
            
            return [job['job_id'] for job in response.data] if response.data else []
        except Exception as e:
            print(f"❌ StatusManager: Error getting stuck jobs: {e}")
            return []

# Create a global instance for easy access
status_manager = StatusManager()

if __name__ == '__main__':
    # Test the status manager
    print("🧪 Testing Status Manager...")
    print("=" * 60)
    
    manager = StatusManager()
    
    # Test connection
    if manager.supabase:
        print("✅ Supabase connection: OK")
    else:
        print("❌ Supabase connection: FAILED")
    
    # Test statistics
    stats = manager.get_job_statistics()
    print(f"\n📊 Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Test cleanup
    deleted = manager.cleanup_old_jobs(days_old=30)
    print(f"\n🗑️  Cleaned up {deleted} old jobs")
    
    # Check for stuck jobs
    stuck_jobs = manager.get_stuck_jobs()
    if stuck_jobs:
        print(f"\n⚠️  Found {len(stuck_jobs)} stuck jobs:")
        for job_id in stuck_jobs:
            print(f"  - {job_id}")
            manager.mark_job_as_stuck(job_id)
    
    print("\n" + "=" * 60)
    print("✅ Status Manager is ready!")