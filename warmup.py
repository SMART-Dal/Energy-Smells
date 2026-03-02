import time

def warmup(duration=2):
    """Busy-waits for a specified duration to wake up the CPU."""
    end_time = time.time() + duration
    while time.time() < end_time:
        pass

if __name__ == "__main__":
    warmup()