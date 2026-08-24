import Foundation

let handle = dlopen("/System/Library/PrivateFrameworks/MediaRemote.framework/MediaRemote", RTLD_NOW)
guard let isPlayingSym = dlsym(handle, "MRMediaRemoteGetNowPlayingApplicationIsPlaying"),
      let getInfoSym = dlsym(handle, "MRMediaRemoteGetNowPlayingInfo") else {
    print("{\"is_playing\": false, \"title\": null, \"artist\": null, \"rate\": 0.0}")
    exit(0)
}

typealias MRMediaRemoteGetNowPlayingApplicationIsPlayingFn = @convention(c) (DispatchQueue, @escaping (Bool) -> Void) -> Void
typealias MRMediaRemoteGetNowPlayingInfoFn = @convention(c) (DispatchQueue, @escaping (CFDictionary?) -> Void) -> Void

let isPlayingFn = unsafeBitCast(isPlayingSym, to: MRMediaRemoteGetNowPlayingApplicationIsPlayingFn.self)
let getInfoFn = unsafeBitCast(getInfoSym, to: MRMediaRemoteGetNowPlayingInfoFn.self)

var isPlayingResult = false
var titleResult: String? = nil
var artistResult: String? = nil
var rateResult: Double = 0.0
var completed = false

isPlayingFn(DispatchQueue.main) { playing in
    isPlayingResult = playing
    getInfoFn(DispatchQueue.main) { dict in
        if let info = dict as? [String: Any] {
            if let t = info["kMRMediaRemoteNowPlayingInfoTitle"] as? String {
                titleResult = t
            }
            if let a = info["kMRMediaRemoteNowPlayingInfoArtist"] as? String {
                artistResult = a
            }
            if let r = info["kMRMediaRemoteNowPlayingInfoPlaybackRate"] as? Double {
                rateResult = r
            } else if let r = info["kMRMediaRemoteNowPlayingInfoPlaybackRate"] as? Float {
                rateResult = Double(r)
            } else if let r = info["kMRMediaRemoteNowPlayingInfoPlaybackRate"] as? Int {
                rateResult = Double(r)
            }
        }
        completed = true
    }
}

let deadline = Date(timeIntervalSinceNow: 0.5)
while !completed && Date() < deadline {
    RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.02))
}

let activePlayback = isPlayingResult || rateResult > 0.0
let titleEscaped = (titleResult ?? "").replacingOccurrences(of: "\"", with: "\\\"")
let artistEscaped = (artistResult ?? "").replacingOccurrences(of: "\"", with: "\\\"")

print("{\"is_playing\": \(activePlayback ? "true" : "false"), \"title\": \"\(titleEscaped)\", \"artist\": \"\(artistEscaped)\", \"rate\": \(rateResult)}")
