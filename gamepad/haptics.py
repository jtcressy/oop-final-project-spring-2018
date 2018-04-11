"""Decorators to use on gamepad functions"""

def fuzzy_vibrate(fn):
    def wrapper(*args, **kwargs):
        #extra functions here
        print("vibrated with fuzzy pattern")
        #call original function
        fn(*args, **kwargs)
        #extra functions after calling orig function
    return wrapper