import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


if __name__ == "__main__":
    dataset_path = Path(ROOT, "dataset", "AnimeSeriesCaptionDataset_t615")
    annotation_path = dataset_path / "annotation.json"
    videos_dir = dataset_path / "videos"

    # Загрузим из него данные
    with open(annotation_path, "r", encoding="utf-8") as f:
        anime_dataset = json.load(f)

    selected_videos = set(Path(data['video_path']) for data in  anime_dataset["animes"])
    print(f"Selected videos: {len(selected_videos)}")

    video_paths: list[Path] = list(videos_dir.glob("*/*.mp4"))
    video_to_delete = [p for p in video_paths if p.relative_to(dataset_path) not in selected_videos]
    print(f"Videos to delete: {len(video_to_delete)}")

    for path in video_to_delete:
        res = input(f"Are you sure to delete {path.relative_to(dataset_path)}? [y/N] ")
        if res.lower() == "y":
            path.unlink()
