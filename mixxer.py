# from docs
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Label, Static, Header, Select
from textual.containers import Container, Horizontal, Vertical
from datetime import datetime
from queue import Queue
from threading import Lock

import numpy as np
import sounddevice as sd
# for audio async (AKA) different thread
import asyncio

class ClockDisplay(Static):
    def on_mount(self) -> None:
        self.set_interval(1, self.update_time)
    def update_time(self) -> None:
        current_time = datetime.now().strftime("%H:%M:%S")
        self.update(f"[b]{current_time}[/b]")

class LevelDisplay(Static):
    def on_mount(self) -> None:
        self.set_interval(0.033, self.update_level) # don't have to configure callback
    def update_level(self) -> None:
        self.update(f"working")

# these need to basically render waveforms with *
class AudioInputDisplay(Static):
    def on_mount(self) -> None:
        self.set_interval(0.01, self.update_display)
    def update_display(self) -> None:
        fix_later = 'fix later'

class AudioOutputDisplay(Static):
    def on_mount(self) -> None:
        self.set_interval(0.01, self.update_display)
    def update_display(self) -> None:
        output_waveform_here = "here"


class AudioThread:
    def __init__(self):
        self.input_queue = Queue()
        self.output_queue = Queue()
        self.samplerate = 44100
        self.channels = 2
        self.blocksize = 512
        self.stream_lock = Lock()
        self.current_input = None
        self.current_output = None
        self.input_stream = None
        self.output_stream = None
        self.running = False

    def input_callback(self, indata, frames, time, status):
        self.input_queue.put((indata.copy(),time.currentTime))

    def output_callback(self, outdata, frames, time, status):
        try: 
            data, _ = self.output_queue.get_nowait()
            outdata[:] = data
        except:
            outdata[:] = 0
    
    def update_devices(self, input_device, output_device):
        with self.stream_lock:
            was_running = self.running
            if was_running:
                self._stop_streams()

            self.current_input = input_device
            self.current_output = output_device

            if was_running:
                self._start_streams()
    
    def _start_streams(self):
        if self.current_input is not None:
            self.input_stream = sd.InputStream(
                    device=self.current_input,
                    samplerate=self.samplerate,
                    channels=self.channels,
                    blocksize=self.blocksize,
                    callback=self.input_callback
                    )
            self.input_stream.start()
        
        if self.current_output is not None:
            self.output_stream = sd.OutputStream(
                    device=self.current_output,
                    samplerate=self.samplerate,
                    channels=self.channels,
                    blocksize=self.blocksize,
                    callback=self.output_callback
                    )
            self.output_stream.start()
        
        self.running = True

    def _stop_streams(self):
        if self.input_stream:
            self.input_stream.stop()
            self.input_stream.close()
            self.input_stream = None

        if self.output_stream:
            self.output_stream.stop()
            self.output_stream.close()
            self.output_stream = None

        self.running = False

    def start(self):
        with self.stream_lock:
            self._start_streams()

    def stop(self):
        with self.stream_lock:
            self._stop_streams()


# splitting these up so i can display them differently with css

class MyApp(App):
    # you can stylize everthing with css this way its super cool.
    CSS = """
    Screen {
        background: white;
    }
    #main{
        layout: horizontal;
    }
    #devices{
        layout: vertical;
    }
    #clock-container{
        height: 3;
        border: solid black;
        background: white;
        color: black;
        content-align: center middle;
    }
    #level-container{
        height: 92%;
        width: 12;
        border: solid black;
        background: white;
        color: black;
        content-align: center middle;
    }
    #device-container{
        width: 1fr;
        border: red;
        background: white;
        color: black;
        content-align: center middle;
    }
    #input-device{
        border: magenta;
        background: white;
    }
    #output-device{
        border: blue;
        background: white;
    }
    #mixxer{
        color: magenta;
        text-style: bold;
    }
    """
    #where you do position init
    def compose(self) -> ComposeResult:
        yield Label("[red]mi[/red][green]xx[/green][blue]er[/blue]", id="mixxer")
        yield Container(
            ClockDisplay(),
            id="clock-container"
        )
        with Horizontal(id="main"):
            yield Container(
                LevelDisplay(),
                id="level-container"
            )
            with Vertical(id="devices"):
                yield Select(id="input-device", options=[("loading...",None)])
                yield Select(id="output-device", options=[("loading...",None)])
    # where you do logic init
    def on_mount(self) -> None:
        self.audio_thread = AudioThread()
        no_device = "off"
        input_devices = [
                (f"{dev['name']} (Inputs: {dev['max_input_channels']})", idx) for idx, dev in enumerate(sd.query_devices()) if dev['max_input_channels'] > 0
                ]
        output_devices = [
                (f"{dev['name']} (Outputs: {dev['max_output_channels']})", idx) for idx, dev in enumerate(sd.query_devices()) if dev['max_output_channels'] > 0
                ]
        select_input = self.query_one("#input-device")
        select_output = self.query_one("#output-device")
        select_input.set_options(input_devices)
        select_output.set_options(output_devices)
        if input_devices:
            select_input.value = input_devices[0][1]
        if output_devices:
            select_output.value = output_devices[0][1]

        self.title = "textual hellow world"
        self.sub_title = "simple tui example"
        
        self.audio_thread.start()


    @on(Select.Changed)
    def select_changed(self, event: Select.Changed) -> None:
        if not hasattr(self, 'audio_thread'):
            return
        
        
        input_dev = self.query_one("#input-device").value
        output_dev = self.query_one("#output-device").value

        if input_dev is not None or output_dev is not None:
            self.audio_thread.update_devices(input_dev,output_dev)
        

    def on_unmount(self):
        if hasattr(self, 'audio_thread'):
            self.audio_thread.stop()



if __name__ == "__main__":
    app = MyApp()
    app.run()
