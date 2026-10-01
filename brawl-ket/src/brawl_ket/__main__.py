if __name__ == "__main__":
    try:
        from brawl_ket.main import main
        main()
    except ImportError:
        # Task 8 hasn't been implemented yet; importing is fine, running is not.
        pass
