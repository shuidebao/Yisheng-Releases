(function (root) {
  "use strict";

  function enqueueLatest(queue, chunk, limit = 2) {
    let dropped = 0;
    while (queue.length >= limit) { queue.shift(); dropped += 1; }
    queue.push(chunk);
    return dropped;
  }

  function adjacentCapture(previous, chunk) {
    return Boolean(previous && previous._sessionId === chunk.sessionId
      && previous.audio_source === chunk.audioSource
      && previous._sequence + 1 === chunk.sequence
      && Number.isFinite(previous._endedAt) && Number.isFinite(chunk.startedAt)
      && chunk.startedAt - previous._endedAt >= -1.2
      && chunk.startedAt - previous._endedAt <= .15);
  }

  function recognitionPlan(previous, chunk) {
    const adjacent = adjacentCapture(previous, chunk);
    const continuous = adjacent && chunk.continuation === true;
    const confident = continuous && Number(previous?.language_probability) >= .7
      && ["zh", "ja", "en"].includes(previous?.language);
    const language = chunk.language === "auto" && confident ? previous.language : chunk.language;
    const context = continuous && previous.target_language === chunk.target
      && language !== "auto" && previous.language === language
      && typeof previous.original === "string" && previous.original.length <= 180
      ? previous.original : "";
    return { language, context };
  }

  function concatenate(parts, length) {
    const output = new Float32Array(length);
    let offset = 0;
    for (const part of parts) { output.set(part, offset); offset += part.length; }
    return output;
  }

  // Energy endpointing is deliberately small: 600 ms of quiet ends a sentence.
  // Only a maximum-length cut carries audio into the next chunk.
  class MicrophoneSegmenter {
    constructor(sampleRate, options = {}) {
      this.sampleRate = sampleRate;
      this.maxFrames = Math.round(sampleRate * (options.maxSeconds || 8));
      this.overlapFrames = Math.round(sampleRate * (options.overlapSeconds || .6));
      this.pauseFrames = Math.round(sampleRate * .6);
      this.preRollFrames = Math.round(sampleRate * .2);
      this.threshold = options.threshold ?? .004;
      this.cursor = 0;
      this.sequence = 0;
      this.reset();
    }

    reset() {
      this.parts = [];
      this.frames = 0;
      this.newFrames = 0;
      this.voiceFrames = 0;
      this.quietFrames = 0;
      this.active = false;
      this.continuation = false;
    }

    retain(frameCount) {
      const count = Math.min(this.frames, frameCount);
      const tail = concatenate(this.parts, this.frames).slice(this.frames - count);
      this.parts = count ? [tail] : [];
      this.frames = count;
    }

    emit(hardCut) {
      let chunk = null;
      if (this.newFrames >= this.sampleRate * .25 && this.voiceFrames >= this.sampleRate * .04) {
        chunk = {
          samples: concatenate(this.parts, this.frames),
          duration: this.frames / this.sampleRate,
          sequence: ++this.sequence,
          continuation: this.continuation,
          startedAt: (this.cursor - this.frames) / this.sampleRate,
          endedAt: this.cursor / this.sampleRate,
        };
      }
      if (hardCut && chunk) {
        this.retain(this.overlapFrames);
        this.newFrames = 0;
        this.voiceFrames = 0;
        this.quietFrames = 0;
        this.continuation = true;
      } else {
        this.reset();
      }
      return chunk;
    }

    push(samples) {
      const emitted = [];
      const frameSize = Math.max(1, Math.round(this.sampleRate * .02));
      for (let offset = 0; offset < samples.length; offset += frameSize) {
        const block = samples.slice(offset, offset + frameSize);
        this.cursor += block.length;
        let energy = 0;
        for (const value of block) energy += value * value;
        const voiced = Math.sqrt(energy / block.length) >= this.threshold;
        if (!this.active && !voiced) {
          this.parts.push(block);
          this.frames += block.length;
          if (this.frames > this.preRollFrames) this.retain(this.preRollFrames);
          continue;
        }
        this.active = true;
        this.parts.push(block);
        this.frames += block.length;
        this.newFrames += block.length;
        if (voiced) { this.voiceFrames += block.length; this.quietFrames = 0; }
        else this.quietFrames += block.length;
        const paused = this.quietFrames >= this.pauseFrames;
        if (paused || this.frames >= this.maxFrames) {
          const chunk = this.emit(!paused);
          if (chunk) emitted.push(chunk);
        }
      }
      return emitted;
    }

    finish() { return this.active ? this.emit(false) : (this.reset(), null); }
  }

  const helpers = { enqueueLatest, adjacentCapture, recognitionPlan, MicrophoneSegmenter };
  if (typeof module !== "undefined" && module.exports) module.exports = helpers;
  root.YishengAudioSession = helpers;
})(typeof globalThis !== "undefined" ? globalThis : this);
