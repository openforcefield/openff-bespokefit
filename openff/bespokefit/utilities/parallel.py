from multiprocessing import Pool
from typing import Optional

from tqdm import tqdm


def apply_async(
    func,
    iterable,
    n_processes: Optional[int] = 1,
    verbose: bool = False,
    description: Optional[str] = None,
):

    if n_processes is not None and n_processes < 2:

        return [
            func(*args)
            for args in tqdm(
                iterable,
                total=len(iterable),
                ncols=80,
                desc=description,
                disable=verbose is False,
            )
        ]

    with Pool() as pool:

        outputs = [pool.apply_async(func, args) for args in iterable]

        return [
            task.get()
            for task in tqdm(
                outputs,
                total=len(outputs),
                ncols=80,
                desc=description,
                disable=verbose is False,
            )
        ]
