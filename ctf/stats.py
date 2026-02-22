import json
import logging
import os
import statistics
import subprocess
from datetime import datetime

import rich
import typer
from typing_extensions import Annotated

from ctf.logger import LOG
from ctf.utils import find_ctf_root_directory, parse_track_yaml

try:
    import pybadges

    _has_pybadges = True
except ImportError:
    _has_pybadges = False

try:
    import matplotlib.pyplot as plt

    _has_matplotlib = True
except ImportError:
    _has_matplotlib = False

app = typer.Typer()


@app.command(
    help="Generate statistics (such as number of tracks, number of flags, total flag value, etc.) from all the `track.yaml files. Outputs as JSON."
)
def stats(
    tracks: Annotated[
        list[str],
        typer.Option(
            "--tracks",
            "-t",
            help="Name of the tracks to count in statistics (if not specified, all tracks are counted).",
        ),
    ] = [],
    generate_badges: Annotated[
        bool,
        typer.Option(
            "--generate-badges",
            help="Generate SVG files of some statistics in the .badges directory.",
        ),
    ] = False,
    charts: Annotated[
        bool,
        typer.Option(
            "--charts",
            help="Generate PNG charts of some statistics in the .charts directory.",
        ),
    ] = False,
    historical: Annotated[
        bool,
        typer.Option(
            "--historical",
            help="Use in conjunction with --charts to generate historical data. ONLY USE THIS IF YOU KNOW WHAT YOU ARE DOING. THIS IS BAD CODE THAT WILL FUCK YOUR REPO IN UNEXPECTED WAYS.",
        ),
    ] = False,
) -> None:
    LOG.debug(msg="Generating statistics...")
    stats = {}
    distinct_tracks: set[str] = set()
    for entry in os.listdir(
        (challenges_directory := os.path.join(find_ctf_root_directory(), "challenges"))
    ):
        if os.path.isdir(
            (track_directory := os.path.join(challenges_directory, entry))
        ) and os.path.isfile(os.path.join(track_directory, "track.yaml")):
            if not tracks:
                distinct_tracks.add(entry)
            elif entry in tracks:
                distinct_tracks.add(entry)

    stats["number_of_tracks"] = len(distinct_tracks)
    stats["number_of_tracks_integrated_with_scenario"] = 0
    stats["number_of_flags"] = 0
    stats["highest_value_flag"] = 0
    stats["most_flags_in_a_track"] = 0
    stats["total_flags_value"] = 0
    stats["number_of_services"] = 0
    stats["number_of_files"] = 0
    stats["median_flag_value"] = 0
    stats["mean_flag_value"] = 0
    stats["number_of_services_per_port"] = {}
    stats["flag_count_per_value"] = {}
    stats["number_of_challenge_designers"] = 0
    stats["number_of_flags_per_track"] = {}
    stats["number_of_points_per_track"] = {}
    stats["not_integrated_with_scenario"] = []
    stats["qa_not_done"] = []
    challenge_designers = set()
    flags = []
    for track in distinct_tracks:
        track_yaml = parse_track_yaml(track_name=track)
        number_of_flags = len(track_yaml["flags"])
        stats["number_of_flags_per_track"][track] = number_of_flags
        if track_yaml["integrated_with_scenario"]:
            stats["number_of_tracks_integrated_with_scenario"] += 1
        else:
            stats["not_integrated_with_scenario"].append(track)
        if number_of_flags > stats["most_flags_in_a_track"]:
            stats["most_flags_in_a_track"] = number_of_flags
        stats["number_of_flags"] += number_of_flags
        stats["number_of_services"] += len(track_yaml["services"])
        stats["number_of_points_per_track"][track] = 0
        for flag in track_yaml["flags"]:
            flags.append(flag["value"])
            stats["number_of_points_per_track"][track] += flag["value"]
            stats["total_flags_value"] += flag["value"]
            if flag["value"] > stats["highest_value_flag"]:
                stats["highest_value_flag"] = flag["value"]
            if flag["value"] not in stats["flag_count_per_value"]:
                stats["flag_count_per_value"][flag["value"]] = 0
            stats["flag_count_per_value"][flag["value"]] += 1
        for service in track_yaml["services"]:
            if service["port"] not in stats["number_of_services_per_port"]:
                stats["number_of_services_per_port"][service["port"]] = 0
            stats["number_of_services_per_port"][service["port"]] += 1
        track_designers = set()
        for challenge_designer in track_yaml["contacts"]["dev"]:
            challenge_designers.add(challenge_designer.lower())
            track_designers.add(challenge_designer)
        qa = set()
        for qa_member in track_yaml["contacts"].get("qa", []):
            qa.add(qa_member.lower())
        if not qa - track_designers:
            stats["qa_not_done"].append(track)

        if os.path.exists(
            path=(files_directory := os.path.join(challenges_directory, track, "files"))
        ):
            for file in os.listdir(path=files_directory):
                stats["number_of_files"] += 1
    stats["median_flag_value"] = statistics.median(flags)
    stats["mean_flag_value"] = round(statistics.mean(flags), 2)
    stats["number_of_challenge_designers"] = len(challenge_designers)

    # Sort dict keys
    stats["flag_count_per_value"] = {
        key: stats["flag_count_per_value"][key]
        for key in sorted(stats["flag_count_per_value"].keys())
    }
    stats["number_of_services_per_port"] = {
        key: stats["number_of_services_per_port"][key]
        for key in sorted(stats["number_of_services_per_port"].keys())
    }

    stats["challenge_designers"] = sorted(list(challenge_designers))
    stats["number_of_flags_per_track"] = dict(
        sorted(stats["number_of_flags_per_track"].items(), key=lambda item: item[1])
    )
    stats["number_of_points_per_track"] = dict(
        sorted(stats["number_of_points_per_track"].items(), key=lambda item: item[1])
    )

    rich.print(json.dumps(stats, indent=2, ensure_ascii=False))
    if generate_badges:
        if not _has_pybadges:
            LOG.critical(msg="Module pybadges was not found.")
            exit(code=1)
        LOG.info(msg="Generating badges...")
        os.makedirs(name=".badges", exist_ok=True)
        write_badge(
            "flag",
            pybadges.badge(left_text="Flags", right_text=str(stats["number_of_flags"])),  # type: ignore
        )
        write_badge(
            "points",
            pybadges.badge(  # type: ignore
                left_text="Points", right_text=str(stats["total_flags_value"])
            ),
        )
        write_badge(
            "tracks",
            pybadges.badge(  # type: ignore
                left_text="Tracks", right_text=str(stats["number_of_tracks"])
            ),
        )
        write_badge(
            "services",
            pybadges.badge(  # type: ignore
                left_text="Services", right_text=str(stats["number_of_services"])
            ),
        )
        write_badge(
            "designers",
            pybadges.badge(  # type: ignore
                left_text="Challenge Designers",
                right_text=str(stats["number_of_challenge_designers"]),
            ),
        )
        write_badge(
            "files",
            pybadges.badge(  # type: ignore
                left_text="Files",
                right_text=str(stats["number_of_files"]),
            ),
        )
        write_badge(
            "scenario",
            pybadges.badge(  # type: ignore
                left_text="Integrated with scenario",
                right_text=str(stats["number_of_tracks_integrated_with_scenario"])
                + "/"
                + str(stats["number_of_tracks"]),
            ),
        )
        write_badge(
            "qa_done",
            pybadges.badge(  # type: ignore
                left_text="QA Done",
                right_text=str(stats["number_of_tracks"] - len(stats["qa_not_done"]))
                + "/"
                + str(stats["number_of_tracks"]),
            ),
        )

    if charts:
        if not _has_matplotlib:
            LOG.critical(msg="Module matplotlib was not found.")
            exit(code=1)
        LOG.info(msg="Generating charts...")
        mpl_logger = logging.getLogger("matplotlib")
        mpl_logger.setLevel(logging.INFO)
        os.makedirs(name=".charts", exist_ok=True)
        # Flag count per value barchart

        fig, ax1 = plt.subplots()
        width = 0.3

        number_of_points = []
        for value, count in stats["flag_count_per_value"].items():
            number_of_points.append(value * count)

        ax1.bar(
            list(stats["flag_count_per_value"].keys()),
            list(stats["flag_count_per_value"].values()),
            -width,
            label="Number of flags",
            color="blue",
            align="edge",
        )
        ax1.set_xlabel("Flag Value (points)")
        ax1.set_ylabel("Number of Flags", color="blue")
        ax1.tick_params(axis="y", labelcolor="blue")

        ax2 = ax1.twinx()

        ax2.bar(
            list(stats["flag_count_per_value"].keys()),
            number_of_points,
            width,
            label="Number of points",
            color="orange",
            align="edge",
        )
        ax2.set_xlabel("Flag Value")
        ax2.set_ylabel("Number of points", color="orange")
        ax2.tick_params(axis="y", labelcolor="orange")

        plt.xticks(
            ticks=range(0, max(stats["flag_count_per_value"].keys()) + 1), rotation=45
        )

        plt.grid(True, linestyle="--", alpha=0.3)
        plt.xlabel("Flag Value")
        plt.title("Number of Flags per Value")
        fig.legend(loc="upper right")

        plt.savefig(os.path.join(".charts", "flags_per_value.png"))
        plt.clf()

        # Number of flag per track barchart
        plt.bar(
            list(stats["number_of_flags_per_track"].keys()),
            stats["number_of_flags_per_track"].values(),
        )
        plt.xticks(ticks=list(stats["number_of_flags_per_track"].keys()), rotation=90)
        plt.grid(True, linestyle="--", alpha=0.3)
        plt.subplots_adjust(bottom=0.5)
        plt.xlabel("Track")
        plt.ylabel("Number of flags")
        plt.title("Number of flags per track")
        plt.savefig(os.path.join(".charts", "flags_per_track.png"))
        plt.clf()

        # Number of points per track barchart
        plt.bar(
            list(stats["number_of_points_per_track"].keys()),
            stats["number_of_points_per_track"].values(),
        )
        plt.xticks(ticks=list(stats["number_of_points_per_track"].keys()), rotation=90)
        plt.grid(True, linestyle="--", alpha=0.3)
        plt.subplots_adjust(bottom=0.5)
        plt.xlabel("Track")
        plt.ylabel("Number of points")
        plt.title("Number of points per track")
        plt.savefig(os.path.join(".charts", "points_per_track.png"))
        plt.clf()

        if historical:
            # Number of points and flags over time
            historical_data = {}
            commit_list = (
                subprocess.check_output(
                    ["git", "log", "--pretty=format:%H %ad", "--date=iso"]
                )
                .decode()
                .splitlines()[::-1]
            )
            commit_list_with_date = []
            for commit in commit_list:
                hash, date = commit.split(" ", 1)
                parsed_datetime = datetime.strptime(date, "%Y-%m-%d %H:%M:%S %z")
                commit_list_with_date.append((parsed_datetime, hash))
            commit_list_with_date = sorted(commit_list_with_date, key=lambda x: x[0])
            subprocess.run(["git", "stash"], check=True)
            for i, commit in list(enumerate(commit_list_with_date))[0:]:
                parsed_datetime, hash = commit
                # Check if the commit message has "Merge pull request" in it
                commit_message = subprocess.run(
                    ["git", "show", "-s", "--pretty=%B", hash],
                    check=True,
                    capture_output=True,
                )
                if "Merge pull request" in commit_message.stdout.decode():
                    LOG.debug(
                        f"{i + 1}/{len(commit_list_with_date)} Checking out commit: {commit}"
                    )
                    parsed_date = parsed_datetime.date()
                    subprocess.run(
                        ["git", "checkout", hash], check=True, capture_output=True
                    )

                    # Execute your command here (replace with what you need)
                    result = (
                        subprocess.run(
                            ["ctf", "stats"],
                            check=False,
                            capture_output=True,
                            text=True,
                        ),
                    )
                    if result[0].returncode == 0:
                        stats = json.loads(result[0].stdout)
                        total_points = stats["total_flags_value"]
                        total_flags = stats["number_of_flags"]
                        print(total_flags)
                        historical_data[parsed_date] = {
                            "total_points": total_points,
                            "total_flags": total_flags,
                        }
            subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)
            subprocess.run(["git", "stash", "pop"], check=True)

            plt.plot(
                historical_data.keys(),
                [data["total_points"] for data in historical_data.values()],
                label="Total Points",
            )
            # plt.plot(historical_data.keys(), [data["total_flags"] for data in historical_data.values()], label="Total Flags")
            # plt.xticks(ticks=list(stats["number_of_points_per_track"].keys()), rotation=90)
            plt.grid(True, linestyle="--", alpha=0.3)
            plt.subplots_adjust(bottom=0.1)
            plt.xlabel("Time")
            plt.ylabel("Total points")
            plt.title("Total points over time")
            plt.xticks(rotation=90)
            plt.subplots_adjust(bottom=0.2)
            plt.subplot().set_ylim(
                0, max([data["total_points"] for data in historical_data.values()]) + 10
            )
            plt.savefig(os.path.join(".charts", "points_over_time.png"))
            plt.clf()

    LOG.debug(msg="Done...")


def write_badge(name: str, svg: str) -> None:
    with open(
        file=os.path.join(".badges", f"badge-{name}.svg"), mode="w", encoding="utf-8"
    ) as f:
        f.write(svg)
