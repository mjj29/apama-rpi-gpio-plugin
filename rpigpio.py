from apama.eplplugin import EPLAction, EPLPluginBase, Correlator, Event, Any
from gpiozero import LightSensor
import threading, queue

class Job(object):
	"""
		Jobs to be executed asynchronously
		@param fn a functor to execute
	"""
	def __init__(self, pin, threshold, fn):
		self.pin = pin
		self.threshold = threshold
		self.fn = fn

def iothread(plugin):
	"""
		Background thread to execute async jobs on.
	"""
	plugin.getLogger().debug("Starting background IO thread for asynchronous jobs")
	ldrs = {}
	while plugin.running:
		try:
			job = plugin.queue.get(timeout=1.0)
			ldrs[job.pin] = (LightSensor(job.pin), job.threshold, job.fn, job.threshold)
		except queue.Empty:
			pass
		except Exception as e:
			plugin.getLogger().error("Exception adding light sensor: "+e)
		try:
			for p in ldrs:
				(pin, threshold, fn, oldvalue) = ldrs[p]
				v = pin.value
				if v > threshold and oldvalue < threshold or v < threshold and oldvalue > threshold:
					fn(v)
				ldrs[p] = (pin, threshold, fn, v)
		except Exception as e:
			plugin.getLogger().error("Exception checking light sensors: "+e)

	plugin.getLogger().info("iothread done")


class RPiGPIOPluginClass(EPLPluginBase):
	"""
	"""
	def __init__(self, init):
		super(RPiGPIOPluginClass, self).__init__(init)
		self.running = True
		self.queue = queue.SimpleQueue()
		self.thread = threading.Thread(target=iothread, args=[self], name='Apama RPiGPIOPluginClass io thread')
		self.thread.start()

	def _sendResponseEvent(self, channel, eventType, body):
		Correlator.sendTo(channel, Event(eventType, body))

	@EPLAction("action<integer, float, string>")
	def startLightSensor(self, pin, threshold, channel):
		self.queue.put(Job(pin, threshold,
			lambda newvalue: self._sendResponseEvent(channel, "com.apamax.LightThreshold", {
				"pin": pin,
				"threshold": threshold,
				"value": newvalue,
				"state": True if newvalue>threshold else False,
			})
		))
		
	@EPLAction("action<>")
	def shutdown(self):
		"""
			Plug-in function to shutdown the background thread.
		"""
		self.getLogger().debug(f"Shutting down RPi GPIO plug-in")
		self.running = False
		self.thread.join()



