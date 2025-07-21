import csv
from datetime import datetime, timedelta, date, time
from db.sql import WordFrequencyQuery, ArticleFrequencyQuery
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
    start_date = end_date - timedelta(days=(7 * 365) - 1)

    words_to_check = [
        ("stýrivextir", "kk"),
        ("verðbólga", "kvk")
    ]

    for stem, cat in words_to_check:
        output_filename = f"{stem}.csv"
        print(f"Querying daily frequency for '{stem}' (category: {cat}) from {start_date.date()} to {end_date.date()}...")

        with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(['date', 'count', 'article_count'])

            word_freq = WordFrequencyQuery.frequency(
                stem=stem,
                cat=cat,
                start=start_date,
                end=end_date,
                timeunit="day"
            )

            article_freq = ArticleFrequencyQuery.frequency(
                stem=stem,
                cat=cat,
                start=start_date,
                end=end_date,
                timeunit="day"
            )

            # Create dictionaries for quick lookup
            word_freq_dict = {d: c for d, c in word_freq}
            article_freq_dict = {d: c for d, c in article_freq}

            # Get all unique dates from both queries
            all_dates = sorted(list(set(word_freq_dict.keys()) | set(article_freq_dict.keys())))

            rows_written = 0
            for d in all_dates:
                count = word_freq_dict.get(d, 0)
                article_count = article_freq_dict.get(d, 0)
                csv_writer.writerow([d, count, article_count])
                rows_written += 1

            if rows_written > 0:
                print(f"  Wrote {rows_written} rows to {output_filename}.")
            else:
                print(f"  No frequency data found for '{stem}' for the given period.")

        print(f"CSV file '{output_filename}' has been created.")
        print("-" * 30)

if __name__ == "__main__":
    get_frequencies_to_csv_per_word()
