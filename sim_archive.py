from enum import Enum


class TaskStatus(Enum):
    NOT_ACTIVE = 0
    ACTIVE = 1
    COMPLETE = 2


class Job:
    def __init__(self, cpu, gpu, mem, time, previous_job=None, next_job=None):
        # Resource constraints (clamped 0 to 1)
        self.cpu = max(0, min(1, cpu))
        self.gpu = max(0, min(1, gpu))
        self.mem = max(0, min(1, mem))
        self.time = time
        self.start_time = -1
        self.end_time = -1
        self.status = TaskStatus.NOT_ACTIVE
        # Bi-directional links
        self.next_job = next_job
        self.previous_job = previous_job

    def __repr__(self):
        p = "Bound" if self.previous_job else "None"
        n = "Bound" if self.next_job else "None"
        return (
            f"Job(CPU={self.cpu}, GPU={self.gpu}, Mem={self.mem}, "
            f"Time={self.time}s, Prev={p}, Next={n}, Status={self.status})"
        )
    
    def schedule(self, stime):
        """
        Marks the job as ACTIVE at stime.
        Raises RuntimeError if the previous job in the chain is not yet complete.
        """
        if self.previous_job is not None and self.previous_job.status != TaskStatus.COMPLETE:
            raise RuntimeError(
                f"Cannot schedule job: previous job must be COMPLETE before this job "
                f"can start (previous job status={self.previous_job.status})"
            )
        self.status = TaskStatus.ACTIVE
        self.start_time = stime

    # def schedule(self, stime):
    #     if self.previous_job and self.previous_job.status != TaskStatus.COMPLETE:
    #         raise Exception("Cannot schedule job: predecessor not complete")
    #     self.status = TaskStatus.ACTIVE
    #     self.start_time = stime

    def complete(self, etime):
        if self.status != TaskStatus.ACTIVE:
            return -1
        if etime < self.start_time + self.time:
            return -1
        self.status = TaskStatus.COMPLETE
        self.end_time = self.start_time + self.time
        return self.end_time

    def is_complete_at(self, current_time):
        return (
            self.status == TaskStatus.ACTIVE
            and self.start_time != -1
            and current_time >= self.start_time + self.time
        )

    def tick(self, current_time):
        if self.is_complete_at(current_time):
            self.complete(self.start_time + self.time)


class Application:
    def __init__(self, deadline, arrival_time=0):
        self.deadline = deadline
        self.arrival_time = arrival_time
        self.app_status = TaskStatus.NOT_ACTIVE
        self.active_job_index = -1  # -1 = none active
        self.jobs = []

    def add_job(self, job):
        """Adds a Job and maintains the doubly-linked chain. Supports method chaining."""
        if self.jobs:
            prev_job = self.jobs[-1]
            prev_job.next_job = job
            job.previous_job = prev_job
        self.jobs.append(job)
        return self

    def get_schedulable_job(self):
        """
        Returns (job, earliest_start_time) for the next job ready to be scheduled,
        or None if the chain is blocked or all jobs are done.
        """
        for job in self.jobs:
            if job.status != TaskStatus.NOT_ACTIVE:
                continue

            if job.previous_job is None:
                # First job: can start any time after application arrival
                return (job, self.arrival_time)

            if job.previous_job.status == TaskStatus.COMPLETE:
                # Predecessor done: earliest start is when it ended
                return (job, job.previous_job.end_time)

            # Predecessor not done: chain is blocked, no point scanning further
            return None

        return None  # all jobs complete or no jobs

    def get_running_jobs(self):

        return [job for job in self.jobs if job.status == TaskStatus.ACTIVE]

    def total_time(self):

        return sum(j.time for j in self.jobs)

    def __repr__(self):
        return (
            f"Application(ArrivalTime={self.arrival_time}, "
            f"Deadline={self.deadline}, "
            f"Jobs={len(self.jobs)}, "
            f"Status={self.app_status})"
        )


class SimulationResult:
    def __init__(self, completed, missed, total_time):
        self.completed = completed
        self.missed = missed
        self.total_time = total_time

    def __repr__(self):
        return (
            f"SimulationResult("
            f"Completed={len(self.completed)}, "
            f"Missed={len(self.missed)}, "
            f"TotalTime={self.total_time})"
        )

    def summary(self):
        print(f"\n=== Simulation Complete at t={self.total_time} ===")
        print(f"  Completed ({len(self.completed)}):")
        for app in self.completed:
            print(f"    {app}")
        print(f"  Missed deadline ({len(self.missed)}):")
        for app in self.missed:
            print(f"    {app}")


class Scheduler:
    def __init__(self, applications):
        self.applications = applications
        self.clock = 0

    def _get_active_resource_usage(self):
        """Sum of cpu, gpu, mem across all currently running jobs in all applications."""
        total_cpu = total_gpu = total_mem = 0.0
        for app in self.applications:
            for job in app.get_running_jobs():
                total_cpu += job.cpu
                total_gpu += job.gpu
                total_mem += job.mem
        return total_cpu, total_gpu, total_mem

    def _has_resource_capacity(self, job):
        total_cpu, total_gpu, total_mem = self._get_active_resource_usage()
        return (
            total_cpu + job.cpu <= 1.0 and
            total_gpu + job.gpu <= 1.0 and
            total_mem + job.mem <= 1.0
        )

    def _get_ready_applications(self):
        return [
            app for app in self.applications
            if app.arrival_time <= self.clock
            and app.app_status != TaskStatus.COMPLETE
        ]

    def _try_schedule(self, app):
        result = app.get_schedulable_job()
        if result is None:
            return

        job, earliest = result
        if self.clock >= earliest and self._has_resource_capacity(job):
            job.schedule(self.clock)
            app.app_status = TaskStatus.ACTIVE

    def _try_complete_app(self, app):
        """Mark application complete if all its jobs are done."""
        if all(j.status == TaskStatus.COMPLETE for j in app.jobs):
            app.app_status = TaskStatus.COMPLETE

    def _check_deadlines(self):
        """Return applications that missed their deadline."""
        return [
            app for app in self.applications
            if app.app_status != TaskStatus.COMPLETE
            and self.clock > app.deadline
        ]

    def tick(self):
        self.clock += 1
        ready_apps = self._get_ready_applications()

        for app in ready_apps:
            # 1. Tick running jobs — auto-completes them if time elapsed
            for job in app.get_running_jobs():
                job.tick(self.clock)

            # 2. Try to schedule the next job in the chain
            self._try_schedule(app)

            # 3. Check if the whole application is now done
            self._try_complete_app(app)

    def run(self, until=None):
        while True:
            all_done = all(
                app.app_status == TaskStatus.COMPLETE
                for app in self.applications
            )
            if all_done:
                break
            if until is not None and self.clock >= until:
                break

            self.tick()

        missed = self._check_deadlines()
        completed = [
            app for app in self.applications
            if app.app_status == TaskStatus.COMPLETE
        ]
        return SimulationResult(completed, missed, self.clock)


# --- Example Usage ---
if __name__ == "__main__":
    # app1: two jobs, fits comfortably within deadline
    app1 = Application(deadline=50, arrival_time=0)
    app1.add_job(Job(0.2, 0.1, 0.3, 10))
    app1.add_job(Job(0.3, 0.2, 0.3, 20))

    # app2: tight deadline — will miss
    app2 = Application(deadline=15, arrival_time=0)
    app2.add_job(Job(0.9, 0.8, 0.9, 30))

    # app3: arrives late, low resource footprint
    app3 = Application(deadline=100, arrival_time=20)
    app3.add_job(Job(0.3, 0.2, 0.2, 10))
    app3.add_job(Job(0.1, 0.1, 0.1, 5))

    # app4: high resource job — will be blocked until app2's job frees resources
    app4 = Application(deadline=80, arrival_time=0)
    app4.add_job(Job(0.5, 0.5, 0.4, 15))

    sim = Scheduler([app1, app2, app3, app4])
    result = sim.run()
    result.summary()