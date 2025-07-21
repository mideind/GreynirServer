import csv
from datetime import datetime, timedelta, date, time
from db.sql import WordFrequencyQuery
from settings import Settings

def get_frequencies_to_csv_per_word():
    """
    Calculates the daily frequency of specified words over the last 7 years
    and saves the results to separate CSV files for each word.
    """
    # Initialize settings to connect to the database
    # Settings.read()

    # Set the end date to the end of yesterday to exclude the current, unfinished day.
    today = date.today()
    end_date = datetime.combine(today, time.min) - timedelta(seconds=1)
    start_date = end_date - timedelta(days=7 * 365)  # 7 years back

    words_to_check = [
        # ("stýrivextir", "kk"),
        ("verðbólga", "kvk")
    ]

    for stem, cat in words_to_check:
        output_filename = f"{stem}.csv"
        print(f"Querying daily frequency for '{stem}' (category: {cat}) from {start_date.date()} to {end_date.date()}...")

        with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(['date', 'count'])

            results = WordFrequencyQuery.frequency(
                stem=stem,
                cat=cat,
                start=start_date,
                end=end_date,
                timeunit="day"
            )

            rows_written = 0
            for d, count in results:
                csv_writer.writerow([d, count])
                rows_written += 1

            if rows_written > 0:
                print(f"  Wrote {rows_written} rows to {output_filename}.")
            else:
                print(f"  No frequency data found for '{stem}' for the given period.")

        print(f"CSV file '{output_filename}' has been created.")
        print("-" * 30)

if __name__ == "__main__":
    get_frequencies_to_csv_per_word()
