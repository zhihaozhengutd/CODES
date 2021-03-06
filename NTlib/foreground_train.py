import tensorflow as tf
from NTlib.nn.simple_net import *
from NTlib.preprocess.sampling import *
from NTlib.preprocess.batch_generator import *
import random
import time
class ForegroundTrain(object):
	def __init__(self,input_placer,gold_placer,learn_rate_placer,
			   	 keep_prob,angle_xy = 30,angle_xz = 30,valid_flag = False,valid_num = 2048):
		self.sess = None
		self.saver = None
		self.angle_xy = angle_xy
		self.angle_xz = angle_xz
		self.fg_para_dict = dict()
		self.valid_flag = valid_flag
		if valid_flag:
			self.valid = generate_batch(valid_num, target_angles_xy = angle_xy,target_angles_xz = angle_xz)
		with tf.variable_scope("fg_"+str(angle_xy)+'_'+str(angle_xz)):
			self.get_nn(input_placer,gold_placer,learn_rate_placer,
				   		keep_prob)
	def get_nn(self,input_placer,gold_placer,learn_rate_placer,
			   keep_prob,
			   fc_1_neuron_num = 16, wd = 0.002):
		self.x = input_placer
		self.y_ = gold_placer
		self.l_rate = learn_rate_placer
		self.keep_prob = keep_prob
		with tf.variable_scope("fs_train_nn"):
			self.para_dict = SimpleNet().generate_flow(self.x,self.keep_prob,fc_neuron_num = fc_1_neuron_num, wd = wd)
			h_fc1 = self.para_dict['h_fc1']
		with tf.variable_scope("fs_fc2"):
			W_fc2 = SimpleNet().weight_variable([fc_1_neuron_num, 2])
			b_fc2 = SimpleNet().bias_variable([2])
		h_fc1_drop = tf.nn.dropout(h_fc1, self.keep_prob)
		self.y_conv = tf.nn.softmax(tf.matmul(h_fc1_drop, W_fc2) + b_fc2)
		cross_entropy_mean = -tf.reduce_mean(self.y_ * tf.log(self.y_conv))
		tf.add_to_collection('losses', cross_entropy_mean)
		cross_entropy = tf.add_n(tf.get_collection('losses'), name='total_loss')
		self.train_step = tf.train.AdamOptimizer(self.l_rate).minimize(cross_entropy)
		correct_prediction = tf.equal(tf.argmax(self.y_conv,1), tf.argmax(self.y_,1))
		self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, "float"))
		self.y_res = tf.argmax(self.y_conv,1)
		self.fg_para_dict['h_fc1'] = h_fc1
		self.fg_para_dict['y_conv'] = self.y_conv
		self.fg_para_dict['y_res'] = self.y_res

	def next_batch(self,batch_size):
		return generate_batch(batch_size, target_angles_xy = self.angle_xy,target_angles_xz = self.angle_xz)

	def get_valid_set(self,window_size = 11):
		return self.valid

	def train(self, epic_num = 2,loop_size = 2100,batch_size = 64,learning_rate = 0.01, thres = 0.01,keep_prob = 1.0):
		accuracies = [0.0,0.1,0.2,0.3,0.4]

		for epic in range(epic_num):
			for i in range(loop_size):
				#ts = time.time()
				batch = self.next_batch(batch_size)
				#te = time.time()
				#print('Gen Batch: ', te-ts)
				if i%2000 == 0:
					print(learning_rate)
					valid = self.get_valid_set()
					train_accuracy = self.accuracy.eval(session = self.sess, feed_dict={self.x: valid[0],
											   											self.y_: valid[1],
											   											self.keep_prob: 1.0,
											   											self.l_rate: learning_rate})
					#print corrects
					print("step %d, training accuracy %g"%(i, train_accuracy))
					if np.std(accuracies[-5:]) < thres :
						learning_rate = max(1e-5,learning_rate/2)
						thres /= 2
						accuracies = [0.0,0.1,0.2,0.3,0.4]
					accuracies.append(train_accuracy)
				#corrects = correct_prediction.eval(feed_dict={x1: batch[0],x2: batch[1], y_: batch[2], keep_prob: 1.0,l_rate: learn_rate * (4.0-epic)})
				#reinforce = append_reinforce(corrects,batch,reinforce)
				#ts = time.time()
				self.train_step.run(session = self.sess,feed_dict={self.x: batch[0],
											   			self.y_: batch[1],
											   			self.keep_prob: keep_prob,
											   			self.l_rate: learning_rate})
				#te = time.time()
				#print('Train: ',te-ts)
		#print(accuracies[-1])
	def predict(self,image,batch_size = 1024):
		sx,sy,sz = image.shape
		batches,pos,neg = sampling(image)
		prob_result = np.zeros((sx * sy * sz,2))
		result = np.zeros((sx * sy * sz))
		counter = 0
		for batch in batch_generator(batches,batch_size):
			num = batch.shape[0]
			#print(np.max(batch))
			prob_result[counter:counter+num,:] = self.y_conv.eval(session = self.sess,
									  	   feed_dict = {
									  	   self.x:batch/255.0,
									  	   self.y_:np.zeros((num,2)),
									  	   self.keep_prob:1.0,
									  	   self.l_rate: 0
									   	   })
			result[counter:counter+num] = self.y_res.eval(session = self.sess,
									  	   feed_dict = {
									  	   self.x:batch/255.0,
									  	   self.y_:np.zeros((num,2)),
									  	   self.keep_prob:1.0,
									  	   self.l_rate: 0
									   	   })
			counter += num
		print(np.max(prob_result))
		misc.imsave('test0.png',np.max(np.reshape(prob_result[:,1],(sx,sy,sz)),axis = 0)*255)
		misc.imsave('test1.png',np.max(np.reshape(prob_result[:,1],(sx,sy,sz)),axis = 1)*255)
		misc.imsave('test2.png',np.max(np.reshape(prob_result[:,1],(sx,sy,sz)),axis = 2)*255)
		misc.imsave('testr0.png',np.max(np.reshape(result,(sx,sy,sz)),axis = 0)*255)
		misc.imsave('testr1.png',np.max(np.reshape(result,(sx,sy,sz)),axis = 1)*255)
		misc.imsave('testr2.png',np.max(np.reshape(result,(sx,sy,sz)),axis = 2)*255)
		



