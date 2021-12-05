class JudgerIllegalState(Exception):
    """
    Exception class that indicates the Judger cannot recover from an illegal state.
    We need to exit the program, but it is a situation we have handled and that is excepted.
    The real reason and traceback information should have been logged to both console and log file.
    You can remind the user to check those useful debug information.
    """
    pass


class StreamEOF(Exception):
    """
    Indicate the io stream is closed normally because read(size) method returned empty string.
    """
    pass
