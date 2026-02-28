from enum import Enum

class JobStatus(Enum):
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
        self.status = JobStatus.NOT_ACTIVE
        
        # Bi-directional links
        self.next_job = next_job
        self.previous_job = previous_job

    def __repr__(self):
        # Helper to show if links exist
        p = "Bound" if self.previous_job else "None"
        n = "Bound" if self.next_job else "None"
        return (f"Job(CPU={self.cpu}, GPU={self.gpu}, Mem={self.mem}, "
                f"Time={self.time}s, Prev={p}, Next={n})",f"Job Status = {self.status}")
    
    def set_status(self, new_status):
        if isinstance(new_status, JobStatus):
            self.status = new_status
            # print(f"Status updated to: {self.status.name}")


# Example: Creating a chain of 3 jobs
job1 = Job(0.1, 0.1, 0.2, 10)
job2 = Job(0.5, 0.4, 0.5, 20, previous_job=job1)
job3 = Job(0.9, 0.8, 0.9, 30, previous_job=job2)

# Manually linking forward
job1.next_job = job2
job2.next_job = job3



