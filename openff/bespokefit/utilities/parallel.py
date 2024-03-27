"""Utilities for parallel execution."""

from multiprocessing import Pool

from tqdm import tqdm


def apply_async(
    func,
    iterable,
    n_processes: int | None = 1,
    verbose: bool = False,
    description: str | None = None,
):
    """Asychronously apply this function."""
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
