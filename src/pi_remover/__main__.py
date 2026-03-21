"""
PI Remover CLI Entry Point
===========================
Allows running via: python -m pi_remover

Usage:
    python -m pi_remover -i data.csv -c "Description" --fast
    python -m pi_remover --help
"""

import multiprocessing as mp

if __name__ == "__main__":
    mp.freeze_support()  # Required for Windows
    
    from pi_remover.core import run_cli
    import sys
    
    if len(sys.argv) > 1:
        run_cli()
    else:
        from pi_remover.core import main
        main()
