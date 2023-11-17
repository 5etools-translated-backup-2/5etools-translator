import os
import json
import pathlib


class CacheManager:
    def __init__(self, cacheFilePath: str):
        self.cacheFile = cacheFilePath
        self.cacheDirty = False
        self.cacheData = {}

        self.load()

    def load(self):
        if os.path.exists(self.cacheFile):
            with open(self.cacheFile) as f:
                self.cacheData = json.load(f)
        return self.cacheData

    def sync(self):
        if self.cacheData == {}:
            self.wipeFromDisk()
            return
        if self.cacheDirty:
            os.makedirs(os.path.dirname(self.cacheFile), exist_ok=True)
            with open(f"{self.cacheFile}.swp", mode="w", encoding="utf-8") as f:
                json.dump(self.cacheData, f, indent="\t", ensure_ascii=False)
            os.rename(f"{self.cacheFile}.swp", self.cacheFile)
            self.cacheDirty = False

    def get(self, key):
        return self.cacheData.get(key)

    def set(self, key, value):
        self.cacheData[key] = value
        self.cacheDirty = True

    def delete(self, key):
        del self.cacheData[key]
        self.cacheDirty = True

    def replaceCacheData(self, data: dict):
        self.cacheData = data
        self.cacheDirty = True

    def wipeFromDisk(self):
        pathlib.Path(self.cacheFile).unlink(missing_ok=True)
