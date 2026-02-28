from enum import Enum

class TaskStatus(Enum):
    NOT_ACTIVE = 0
    ACTIVE = 1
    COMPLETE = 2

'''
Docstring for simulator
This is the unit request of consistent job that is represents a single contiguous request. An application profile 
would be a collection of these request.
'''
class Job:
    def __init__(self, cpu, gpu, mem, time, previous_job=None, next_job=None):
        # Resource constraints (clamped 0 to 1)
        self.cpu = max(0, min(1, cpu))
        self.gpu = max(0, min(1, gpu))
        self.mem = max(0, min(1, mem))
        self.time = time      # This mentions how long the task takes to complete
        self.start_time = -1
        self.status = TaskStatus.NOT_ACTIVE
        # Bi-directional links
        self.next_job = next_job
        self.previous_job = previous_job

    def __repr__(self):
        # Helper to show if links exist
        p = "Bound" if self.previous_job else "None"
        n = "Bound" if self.next_job else "None"
        return (f"Job(CPU={self.cpu}, GPU={self.gpu}, Mem={self.mem}, "
                f"Time={self.time}s, Prev={p}, Next={n})",f"Job Status = {self.status}")

    def schedule(self, stime):
        self.status = TaskStatus.ACTIVE
        self.start_time=stime
    
    def complete(self):
        self.status= TaskStatus.COMPLETE

class Application:
    def __init__(self, deadline, start_time=0):
        # deadline: user-provided value
        # start_time: defaults to 0 if not provided
        self.deadline = deadline
        self.start_time = start_time
        
        # Internal list to store our Job objects
        self.jobs = []

    def add_job(self, job):
        """Adds a Job object and handles the linear linking."""
        if self.jobs:
            # Link the new job to the current last job
            prev_job = self.jobs[-1]
            prev_job.next_job = job
            job.previous_job = prev_job
            
        self.jobs.append(job)
        return self

    def __repr__(self):
        return (f"Application(StartTime={self.start_time}, "
                f"Deadline={self.deadline}, Jobs={len(self.jobs)})")

# --- Example Usage ---

# 1. Using the default start_time (0)
app1 = Application(deadline=100)
print(app1) # Output: Application(StartTime=0, Deadline=100, Jobs=0)

# 2. Providing a custom start_time via user input
user_val = int(input("Enter start time: ")) # e.g., 50
app2 = Application(deadline=200, start_time=user_val)
print(app2) # Output: Application(StartTime=50, Deadline=200, Jobs=0)

# Example: Creating a chain of 3 jobs
job1 = Job(0.1, 0.1, 0.2, 10)
job2 = Job(0.5, 0.4, 0.5, 20, previous_job=job1)
job3 = Job(0.9, 0.8, 0.9, 30, previous_job=job2)

# Manually linking forward
job1.next_job = job2
job2.next_job = job3



