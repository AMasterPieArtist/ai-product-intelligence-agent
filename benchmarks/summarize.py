"""Build campaign reports offline from authoritative records and reviews."""
import argparse
try:
    from .campaign_report import collect, write_reports
except ImportError:
    from campaign_report import collect, write_reports


def summarize(folder):
    return write_reports(folder, collect(folder))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('campaign_dir')
    args = parser.parse_args()
    print(summarize(args.campaign_dir))
